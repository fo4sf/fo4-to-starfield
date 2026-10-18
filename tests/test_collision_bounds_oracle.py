"""Synthetic tests for scripts/oracles/collision_bounds.py (no game assets)."""
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "tests"))
from fo4sf import fo4collision, nif, sfcollision, sfnif  # noqa: E402
from test_collision import fake_template
from test_sfbodies import cube, convex_blob, mesh_blob

spec = importlib.util.spec_from_file_location(
    "collision_bounds_oracle",
    Path(__file__).resolve().parents[1] / "scripts/oracles/collision_bounds.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def shape(box, name=b"Prop:0"):
    sphere = (*box[:3], max(box[3:]))
    return sfnif.StaticShape(name, b"a" * 20 + b"\\" + b"b" * 20, 6, 4, "m.mat", sphere, box)


def nif_bytes(mesh_box, collision=None, children=None):
    blob = collision
    extra = children
    return nif.serialize(sfnif.build_static_nif(b"Prop", [shape(mesh_box)],
                                                collision_blob=blob, child_collision_blobs=extra))


class CollisionBoundsOracleTests(unittest.TestCase):
    def test_matching_box_is_clean(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        report = oracle.audit(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box), path="match.nif")
        self.assertEqual(report["flags"], [])
        self.assertEqual(report["collision"]["bodies"], 1)
        self.assertEqual(report["collision"]["per_body"][0]["shape"], "hknpBoxShape")

    def test_missing_collision_is_flagged(self):
        report = oracle.audit(nif_bytes((0, 0, 1, 1, 1, 1)), path="empty.nif")
        self.assertEqual(report["flags"], ["missing"])
        self.assertEqual(report["collision"]["bodies"], 0)

    def test_tiny_collision_is_much_smaller(self):
        tiny = sfcollision.box_blob(fake_template(), (0, 0, 0.01), (0.02, 0.02, 0.01))
        report = oracle.audit(nif_bytes((0, 0, 1, 2, 2, 2), tiny))
        self.assertIn("much_smaller", report["flags"])

    def test_offset_collision_is_flagged(self):
        far = sfcollision.box_blob(fake_template(), (8, 0, 0.5), (0.4, 0.4, 0.5))
        report = oracle.audit(nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), far))
        self.assertIn("offset", report["flags"])

    def test_refr_scale_scales_printed_bounds_not_the_ratio(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        a = oracle.audit(data, scale=1.0)
        b = oracle.audit(data, scale=0.75)
        self.assertEqual(a["flags"], [])
        self.assertEqual(b["flags"], [])
        self.assertAlmostEqual(b["mesh"]["extent"][0], 0.75 * a["mesh"]["extent"][0], places=4)
        self.assertAlmostEqual(b["collision"]["extent"][2], 0.75 * a["collision"]["extent"][2], places=4)

    def test_three_native_bodies_union(self):
        v, f = cube((0, 0, 0), (1, 1, 1))
        blobs = [convex_blob(v, f), convex_blob(*cube((2, 0, 0), (3, 1, 1))),
                 convex_blob(*cube((0, 0, 4), (1, 1, 5)))]
        report = oracle.audit(nif_bytes((1.5, 0.5, 2.5, 1.5, 0.5, 2.5), children=blobs))
        self.assertEqual(report["collision"]["bodies"], 3)
        self.assertEqual(report["collision"]["min"][0], 0.0)
        self.assertEqual(report["collision"]["max"][2], 5.0)
        self.assertEqual(report["flags"], [])

    def test_compressed_mesh_body_is_read_via_sfbodies(self):
        packed = [(0, 0, 0), (100, 0, 0), (100, 100, 0), (0, 100, 0)]
        blob = mesh_blob(packed, [(0, 1, 2, 3)], section_off=(0, 0, 0))
        report = oracle.audit(nif_bytes((0.5, 0.5, 0.0, 0.5, 0.5, 0.01), children=[blob]))
        self.assertEqual(report["collision"]["bodies"], 1)
        self.assertEqual(report["collision"]["per_body"][0]["shape"], "hknpCompressedMeshShape")
        self.assertEqual(report["collision"]["min"][:2], [0.0, 0.0])
        self.assertEqual(report["collision"]["max"][:2], [1.0, 1.0])

    def test_sfcollision_rejects_compressed_mesh_tagfile(self):
        blob = mesh_blob([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2, 2)])
        with self.assertRaises(sfcollision.CollisionError):
            sfcollision.check_template(blob)
        self.assertIn(b"hknpCompressedMeshShape", blob)

    def test_fo4collision_rejects_starfield_box_blob(self):
        blob = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        self.assertEqual(blob[:8], b"\x00\x00\x18\x18TAG0")
        center, half = sfcollision.read_box(blob)
        self.assertAlmostEqual(center[2], 0.5, places=5)
        self.assertAlmostEqual(half[0], 0.4, places=5)
        with self.assertRaises(fo4collision.hkpackfile.PackfileError) as ctx:
            fo4collision.decode(blob)
        self.assertIn("packfile", str(ctx.exception).lower())
        ev = oracle.research_box_vs_packfile(blob)
        self.assertIsInstance(ev["sfcollision"], list)
        self.assertTrue(str(ev["fo4collision"]).startswith("PackfileError"))

    def test_unreadable_blob_is_flagged(self):
        report = oracle.audit(nif_bytes((0, 0, 1, 1, 1, 1), collision=b"not-havok"))
        self.assertIn("unreadable", report["flags"])

    def test_cli_manifest_and_scale(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            model = staging / "meshes" / "roof" / "hatch.nif"
            model.parent.mkdir(parents=True)
            model.write_bytes(data)
            manifest = staging / "manifest.json"
            manifest.write_text(json.dumps({"items": [{"model": "roof/hatch.nif", "scale": 0.75}]}), encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                code = oracle.main(["--manifest", str(manifest), "--staging", str(staging)])
        self.assertEqual(code, 0)

    def test_cli_flags_exit_1(self):
        data = nif_bytes((0, 0, 1, 1, 1, 1))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "empty.nif"
            path.write_bytes(data)
            with redirect_stdout(io.StringIO()):
                code = oracle.main([str(path)])
        self.assertEqual(code, 1)

    def test_matching_body_plus_unreadable_sibling_is_unreadable(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        report = oracle.audit(
            nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box, children=[b"not-havok"]),
            path="partial.nif")
        self.assertIn("unreadable", report["flags"])
        self.assertGreaterEqual(report["collision"]["bodies"], 1)
        self.assertTrue(report.get("errors"))
        self.assertIn("unreadable", oracle.failed([report])[0]["flags"])

    def test_collision_only_nif_is_unassessed(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif.serialize(sfnif.build_static_nif(b"Prop", [], collision_blob=box))
        report = oracle.audit(data, path="collision-only.nif")
        self.assertIn("no_mesh", report["flags"])
        self.assertIsNone(report["mesh"])
        self.assertEqual(report["collision"]["bodies"], 1)
        self.assertTrue(oracle.failed([report]))

    def test_nonfinite_scale_is_rejected(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        for scale in (float("nan"), float("inf"), float("-inf")):
            report = oracle.audit(data, scale=scale, path="scale.nif")
            self.assertIn("unreadable", report["flags"], msg=scale)
            self.assertIsNone(report["scale"])
            payload = json.dumps(report, allow_nan=False)
            self.assertNotIn("NaN", payload)
            self.assertNotIn("Infinity", payload)

    def test_malformed_manifest_entries_are_reported(self):
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        data = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            model = staging / "meshes" / "roof" / "hatch.nif"
            model.parent.mkdir(parents=True)
            model.write_bytes(data)
            reports = oracle.audit_manifest(
                {"items": [
                    {"model": "roof/hatch.nif"},
                    None,
                    {"source": "lost.nif"},
                ]},
                staging)
        self.assertEqual(len(reports), 3)
        self.assertEqual(reports[0]["flags"], [])
        self.assertIn("unreadable", reports[1]["flags"])
        self.assertIn("unreadable", reports[2]["flags"])
        self.assertEqual(len(oracle.failed(reports)), 2)

    def test_cli_codex_fail_open_controls(self):
        script = Path(_ROOT) / "scripts" / "oracles" / "collision_bounds.py"
        box = sfcollision.box_blob(fake_template(), (0, 0, 0.5), (0.4, 0.4, 0.5))
        match = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box)
        sibling = nif_bytes((0, 0, 0.5, 0.4, 0.4, 0.5), box, children=[b"not-havok"])
        collision_only = nif.serialize(sfnif.build_static_nif(b"Prop", [], collision_blob=box))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "match.nif").write_bytes(match)
            (root / "sibling.nif").write_bytes(sibling)
            (root / "collision-only.nif").write_bytes(collision_only)
            staging = root / "stage"
            model = staging / "meshes" / "roof" / "hatch.nif"
            model.parent.mkdir(parents=True)
            model.write_bytes(match)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "items": [
                    {"model": "roof/hatch.nif"},
                    None,
                    {"source": "lost.nif"},
                ]}), encoding="utf-8")

            def run(*args):
                return subprocess.run(
                    [sys.executable, "-I", str(script), *args],
                    capture_output=True, text=True, cwd=str(root))

            sibling_proc = run(str(root / "sibling.nif"))
            self.assertNotEqual(sibling_proc.returncode, 0)
            sibling_out = json.loads(sibling_proc.stdout)
            self.assertIn("unreadable", sibling_out["reports"][0]["flags"])
            self.assertGreaterEqual(sibling_out["reports"][0]["collision"]["bodies"], 1)
            self.assertTrue(sibling_out["reports"][0].get("errors"))

            meshless = run(str(root / "collision-only.nif"))
            self.assertNotEqual(meshless.returncode, 0)
            meshless_out = json.loads(meshless.stdout)
            self.assertIn("no_mesh", meshless_out["reports"][0]["flags"])
            self.assertIsNone(meshless_out["reports"][0]["mesh"])

            for flag in ("nan", "inf", "-inf"):
                proc = run("--scale", flag, str(root / "match.nif"))
                self.assertNotEqual(proc.returncode, 0, msg=flag)
                self.assertNotIn("NaN", proc.stdout)
                self.assertNotIn("Infinity", proc.stdout)

            man = run("--manifest", str(manifest), "--staging", str(staging))
            self.assertNotEqual(man.returncode, 0)
            man_out = json.loads(man.stdout)
            self.assertEqual(man_out["models"], 3)
            self.assertGreaterEqual(man_out["flagged"], 2)
            self.assertEqual(man_out["reports"][0]["flags"], [])
            self.assertIn("unreadable", man_out["reports"][1]["flags"])
            self.assertIn("unreadable", man_out["reports"][2]["flags"])

            ok = run(str(root / "match.nif"))
            self.assertEqual(ok.returncode, 0)
            ok_out = json.loads(ok.stdout)
            self.assertEqual(ok_out["flagged"], 0)
            json.dumps(ok_out, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
