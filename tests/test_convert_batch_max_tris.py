"""--max-tris is off unless asked for: a skipped model drops its base record, which an interior batch's id checks
refuse (batch 6 at fe1c993 lost 178 bases to the 20000 default once 5f2a065 made the option skip meshes)."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class MaxTrisDefaultTests(unittest.TestCase):
    def test_max_tris_defaults_to_off(self):
        tree = ast.parse((ROOT / "scripts" / "convert_batch.py").read_text(encoding="utf-8"))
        defaults = [kw.value.value for call in ast.walk(tree) if isinstance(call, ast.Call)
                    and getattr(call.func, "attr", "") == "add_argument"
                    and call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "--max-tris"
                    for kw in call.keywords if kw.arg == "default"]
        self.assertEqual(defaults, [0])


if __name__ == "__main__":
    unittest.main()
