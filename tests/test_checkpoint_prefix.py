"""Custom output namespaces must keep the complete generated dependency graph."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf import checkpoints, nif, sfnif


def generated(stage, prefix):
    shape = sfnif.StaticShape(b"Synthetic", b"test\\mesh", 3, 3,
        f"materials/{prefix}/test.mat", (0, 0, 0, 1), (0, 0, 0, 1, 1, 1))
    files = {
        f"meshes/{prefix}/chair.nif": nif.serialize(sfnif.build_static_nif(b"Synthetic", [shape])),
        "geometries/test/mesh.mesh": b"synthetic geometry",
        f"materials/{prefix}/test.mat": json.dumps({"texture": f"Data/Textures/{prefix}/color.dds"}).encode(),
        f"textures/{prefix}/color.dds": b"synthetic texture",
    }
    for name, data in files.items():
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {"ok": True, "out_name": f"{prefix}/chair", "fallback_materials": 0, "shapes": 1}, files


class CheckpointPrefixTests(unittest.TestCase):
    def test_default_and_custom_namespaces_track_all_outputs_and_resume(self):
        for prefix, signature in (("fo4port", {}), ("preview", {"prefix": "preview"}),
                                  ("Preview", {"prefix": "Preview"}),
                                  ("preview/doors", {"prefix": "preview/doors"})):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as tmp:
                stage = Path(tmp)
                result, files = generated(stage, prefix)
                cache = checkpoints.Checkpoints(stage, signature)
                self.assertTrue(cache.save("chair.nif", result))
                self.assertEqual(set(cache.expected["chair.nif"]), set(files))
                self.assertEqual(checkpoints.Checkpoints(stage, signature).load("chair.nif"), result)
                self.assertEqual(cache.verify_batch(), [])

    def test_missing_or_changed_custom_materials_and_textures_prevent_reuse(self):
        for prefix in ("preview", "Preview"):
            for kind in ("materials", "textures"):
                for change in ("missing", "changed"):
                    with self.subTest(prefix=prefix, kind=kind, change=change), tempfile.TemporaryDirectory() as tmp:
                        stage = Path(tmp)
                        result, files = generated(stage, prefix)
                        signature = {"prefix": prefix}
                        cache = checkpoints.Checkpoints(stage, signature)
                        cache.save("chair.nif", result)
                        relative = next(name for name in files if name.startswith(kind + "/"))
                        path = stage / relative
                        if change == "missing":
                            path.unlink()
                        else:
                            path.write_bytes(path.read_bytes().replace(b"synthetic", b"different")
                                             if kind == "textures" else b'{"changed": true}')
                        self.assertIsNone(checkpoints.Checkpoints(stage, signature).load("chair.nif"))
                        self.assertIn({"source": "chair.nif", "output": relative}, cache.verify_batch())

    def test_old_incomplete_custom_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = Path(tmp)
            result, _ = generated(stage, "preview")
            cache = checkpoints.Checkpoints(stage, {"prefix": "preview"})
            cache.save("chair.nif", result)
            saved = json.loads(cache.path("chair.nif").read_text())
            saved["outputs"] = {name: digest for name, digest in saved["outputs"].items()
                                if not name.startswith(("materials/", "textures/"))}
            cache.path("chair.nif").write_text(json.dumps(saved))
            self.assertIsNone(checkpoints.Checkpoints(stage, {"prefix": "preview"}).load("chair.nif"))

    def test_direct_inventory_matches_prefix_without_case_sensitivity(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, files = generated(Path(tmp), "Preview")
            self.assertEqual(set(checkpoints.output_inventory(tmp, result, prefix="Preview")), set(files))


if __name__ == "__main__":
    unittest.main()
