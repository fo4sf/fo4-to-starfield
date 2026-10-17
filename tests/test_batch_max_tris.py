"""convert_batch --max-tris is applied: meshes over the limit are skipped and recorded as failures."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
spec = importlib.util.spec_from_file_location("convert_batch_maxtris", root / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class BatchMaxTrisTests(unittest.TestCase):
    def test_skips_over_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            collision = Path(tmp) / "collision.nif"
            collision.write_bytes(b"synthetic")
            cell = Path(tmp) / "cell.json"
            cell.write_text(json.dumps({"refs": [
                {"model": "a\\small.nif", "type": "Static"},
                {"model": "b\\big.nif", "type": "Static"},
            ]}))

            def converter(*args, **kw):
                return SimpleNamespace(stats={}, material_errors={}, convert_nif=lambda name: {
                    "ok": True, "out_name": name.replace("\\", "/").replace(".nif", ""),
                    "shapes": 1, "fallback_materials": 0})

            counts = {"meshes\\a\\small.nif": 100, "meshes\\b\\big.nif": 50000}
            def fake_count(src, name):
                return counts.get(name, 0)

            argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
                    "--content-resources", "unused", "--texconv", "unused",
                    "--collision-template", str(collision), "--cell-json", str(cell),
                    "--max-tris", "10000", "--limit", "10"]
            with patch.object(sys, "argv", argv), \
                    patch.object(batch.pipeline, "Fo4Archives", return_value=SimpleNamespace()), \
                    patch.object(batch.pipeline, "Converter", side_effect=converter), \
                    patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                    patch.object(batch, "triangle_count", side_effect=fake_count), \
                    patch("builtins.print"):
                batch.main()
            manifest = json.loads((staging / "manifest.json").read_text())
            names = [it["source"] for it in manifest["items"]]
            self.assertIn("meshes\\a\\small.nif", names)
            self.assertNotIn("meshes\\b\\big.nif", names)
            self.assertTrue(any("exceeds --max-tris" in f["reason"] for f in manifest.get("failures", [])))


if __name__ == "__main__":
    unittest.main()
