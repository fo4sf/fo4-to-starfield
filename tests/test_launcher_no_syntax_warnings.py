"""The launcher's sources compile without SyntaxWarning (an invalid escape such as "\\S" in a docstring warns on
Python 3.12 and later, and is to become an error); Install saw one on the PC."""
import glob
import os
import unittest
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NoSyntaxWarningTests(unittest.TestCase):
    def test_launcher_sources_compile_cleanly(self):
        paths = sorted(glob.glob(os.path.join(ROOT, "src", "fo4sf", "launcher", "*.py")))
        paths.append(os.path.join(ROOT, "scripts", "launcher.py"))
        for p in paths:
            with self.subTest(path=os.path.relpath(p, ROOT)), open(p, encoding="utf-8") as f:
                src = f.read()
                with warnings.catch_warnings():
                    warnings.simplefilter("error", SyntaxWarning)
                    compile(src, p, "exec")


if __name__ == "__main__":
    unittest.main()
