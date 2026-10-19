"""Synthetic tests for navmesh coverage inventory."""
import errno
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "scripts" / "actors"))
import navmesh_inventory as inv  # noqa: E402


def _main(args):
    argv = ["navmesh_inventory.py", *args]
    with patch.object(sys, "argv", argv):
        return inv.main()


class NavmeshInventoryTests(unittest.TestCase):
    def test_detects_lost_and_reduced(self):
        fo4 = {
            "cellA": {"triangles": 100, "area": 50.0},
            "cellB": {"triangles": 20, "area": 10.0},
            "cellC": {"triangles": 5, "area": 2.0},
        }
        sf = {
            "cellA": {"triangles": 0, "area": 0.0},
            "cellB": {"triangles": 8, "area": 4.0},
            "cellC": {"triangles": 5, "area": 2.0},
            "cellD": {"triangles": 30, "area": 15.0},
        }
        report = inv.inventory(fo4, sf)
        self.assertEqual(len(report["lost_coverage"]), 1)
        self.assertEqual(report["lost_coverage"][0]["cell"], "cellA")
        self.assertEqual(len(report["reduced_coverage"]), 1)
        self.assertEqual(report["reduced_coverage"][0]["cell"], "cellB")
        self.assertEqual(len(report["gained_coverage"]), 1)
        self.assertEqual(report["unchanged"], 1)
        self.assertEqual(report["unknown"], [])
        self.assertEqual(report["lost_triangles"], 100)
        self.assertEqual(report["reduced_triangles_approx"], 12)
        self.assertIn("1 lost", report["summary"])
        self.assertIn("reduced (12 tris approx)", report["summary"])

    def test_reduced_triangle_loss_is_never_negative(self):
        # #208: reduced when either triangles or area fell; count only positive triangle losses.
        report = inv.inventory(
            {"c": {"triangles": 100, "area": 50.0}},
            {"c": {"triangles": 150, "area": 10.0}},
        )
        self.assertEqual([item["cell"] for item in report["reduced_coverage"]], ["c"])
        self.assertEqual(report["reduced_triangles_approx"], 0)

        mixed = inv.inventory(
            {
                "gain": {"triangles": 100, "area": 50.0},
                "loss": {"triangles": 80, "area": 40.0},
            },
            {
                "gain": {"triangles": 150, "area": 10.0},
                "loss": {"triangles": 20, "area": 10.0},
            },
        )
        self.assertEqual(
            [item["cell"] for item in mixed["reduced_coverage"]],
            ["gain", "loss"],
        )
        self.assertEqual(mixed["reduced_triangles_approx"], 60)

    def test_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fo4_path = tmp / "fo4.json"
            sf_path = tmp / "sf.json"
            out_path = tmp / "report.json"
            fo4_path.write_text(json.dumps({"c1": {"triangles": 10, "area": 1.0}}))
            sf_path.write_text(json.dumps({"c1": {"triangles": 0, "area": 0.0}}))
            code = _main(["--fo4-stats", str(fo4_path), "--sf-stats", str(sf_path), "--out", str(out_path)])
            self.assertEqual(code, 0)
            loaded = json.loads(out_path.read_text())
            self.assertEqual(len(loaded["lost_coverage"]), 1)

    def test_cli_refuses_overwrite_of_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fo4_path = tmp / "fo4.json"
            sf_path = tmp / "sf.json"
            payload = json.dumps({"c": {"triangles": 10, "area": 1.0}})
            fo4_path.write_text(payload)
            sf_path.write_text(json.dumps({"c": {"triangles": 0, "area": 0.0}}))
            code = _main(["--fo4-stats", str(fo4_path), "--sf-stats", str(sf_path), "--out", str(fo4_path)])
            self.assertEqual(code, 2)
            self.assertEqual(fo4_path.read_text(), payload)
            alias = tmp / "alias.json"
            try:
                os.link(fo4_path, alias)
            except OSError:
                return
            code = _main(["--fo4-stats", str(fo4_path), "--sf-stats", str(sf_path), "--out", str(alias)])
            self.assertEqual(code, 2)
            self.assertEqual(fo4_path.read_text(), payload)
            self.assertEqual(alias.read_text(), payload)

    def test_cli_rejects_nan_measurements_and_tols(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fo4_path = tmp / "fo4.json"
            sf_path = tmp / "sf.json"
            out_path = tmp / "report.json"
            fo4_path.write_text(json.dumps({"c": {"triangles": 100, "area": 100.0}}))
            sf_path.write_text(json.dumps({"c": {"triangles": 100, "area": float("nan")}}, allow_nan=True))
            code = _main(["--fo4-stats", str(fo4_path), "--sf-stats", str(sf_path), "--out", str(out_path)])
            self.assertEqual(code, 0)
            loaded = json.loads(out_path.read_text())
            self.assertEqual(len(loaded["unknown"]), 1)
            self.assertEqual(loaded["unchanged"], 0)
            out_path.unlink()
            sf_path.write_text(json.dumps({"c": {"triangles": 1, "area": 1.0}}))
            code = _main([
                "--fo4-stats", str(fo4_path), "--sf-stats", str(sf_path),
                "--out", str(out_path), "--area-tol", "nan", "--tri-tol", "nan",
            ])
            self.assertEqual(code, 2)
            self.assertFalse(out_path.exists())

    def test_failed_write_keeps_enospace_and_replaced_owner_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            out = tmp / "report.json"
            real_fdopen = os.fdopen

            def exploding(fd, *args, **kwargs):
                handle = real_fdopen(fd, *args, **kwargs)

                def boom(_data):
                    raise OSError(errno.ENOSPC, "No space left on device")

                handle.write = boom
                return handle

            with patch.object(inv.os, "fdopen", exploding):
                with self.assertRaises(OSError) as caught:
                    inv._write_exclusive(out, "payload")
            self.assertEqual(caught.exception.errno, errno.ENOSPC)
            owner = tmp / "owner.json"
            owner.write_text("owner-bytes")
            if out.exists():
                out.unlink()
            os.replace(owner, out)
            st = out.stat()
            inv._unlink_if_owned(out, st.st_dev, 0)
            self.assertTrue(out.exists())
            self.assertEqual(out.read_text(), "owner-bytes")
            other = tmp / "ours.json"
            other.write_text("ours")
            ours = other.stat()
            # Keep the original inode linked so POSIX cannot reuse it for the replacement.
            held = tmp / "held-inode"
            os.link(other, held)
            other.unlink()
            other.write_text("owner-bytes")
            replaced = other.stat()
            self.assertNotEqual((replaced.st_dev, replaced.st_ino), (ours.st_dev, ours.st_ino))
            inv._unlink_if_owned(other, ours.st_dev, ours.st_ino)
            self.assertTrue(other.exists())
            self.assertEqual(other.read_text(), "owner-bytes")
