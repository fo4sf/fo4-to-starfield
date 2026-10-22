"""--max-tris is off unless asked for: a skipped model drops its base record, which an interior batch's id checks
refuse (batch 6 at fe1c993 lost 178 bases to the 20000 default once 5f2a065 made the option skip meshes)."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("convert_batch_max_tris", ROOT / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)

HEAVY, LIGHT = "meshes/setdressing/heavy.nif", "meshes/setdressing/light.nif"
TRIS = {HEAVY.encode(): 25000, LIGHT.encode(): 10}


def converted(*extra):
    """The sources a synthetic batch of one 25,000-triangle and one 10-triangle model converts."""
    converter = SimpleNamespace(stats={}, material_errors={})
    converter.convert_nif = Mock(side_effect=lambda name: {"ok": True, "out_name": name[:-4], "shapes": 1,
                                                           "fallback_materials": 0})
    src = SimpleNamespace(mesh_names=lambda pattern: [HEAVY, LIGHT], mesh=lambda name: name.encode())
    shapes = lambda raw: [SimpleNamespace(triangles=[(0, 1, 2)] * TRIS[raw])]
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "staging"
        collision = Path(tmp) / "collision.nif"
        collision.write_bytes(b"synthetic")
        argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
                "--content-resources", "unused", "--texconv", "unused",
                "--collision-template", str(collision), *extra]
        with patch.object(sys, "argv", argv), \
                patch.object(batch.pipeline, "Fo4Archives", return_value=src), \
                patch.object(batch.pipeline, "Converter", return_value=converter), \
                patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"), \
                patch.object(batch.nif, "parse", side_effect=lambda raw: raw), \
                patch.object(batch.nif, "fo4_trishapes", side_effect=shapes), \
                patch("builtins.print"):
            batch.main()
        manifest = json.loads((staging / "manifest.json").read_text())
    return sorted(i["source"] for i in manifest["items"])


class MaxTrisDefaultTests(unittest.TestCase):
    def test_a_heavy_model_is_converted_when_max_tris_is_not_given(self):
        self.assertEqual(converted(), [HEAVY, LIGHT])

    def test_a_heavy_model_is_skipped_when_max_tris_is_given(self):
        self.assertEqual(converted("--max-tris", "20000"), [LIGHT])
