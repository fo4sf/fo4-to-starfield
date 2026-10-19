import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from fo4sf.convert_static import class_mass_scale, require_mass_scale

class TestMassScale(unittest.TestCase):
    def test_class_defaults(self):
        self.assertEqual(class_mass_scale("small_misc"), 0.2)
        self.assertEqual(class_mass_scale("unknown", 1.5), 1.5)
        self.assertEqual(class_mass_scale("large_mstt"), 2.0)

    def test_require_still_works(self):
        self.assertEqual(require_mass_scale(0.5), 0.5)
        with self.assertRaises(ValueError):
            require_mass_scale(0)
        with self.assertRaises(ValueError):
            require_mass_scale(-1)

if __name__ == "__main__":
    unittest.main()
