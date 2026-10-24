"""Test git revision in fo4sf status."""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class TestStatusGit(unittest.TestCase):
    def test_git_rev_shown(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        # Use a temp config that won't fail load if we mock, but for simplicity call the helper
        from fo4sf.__main__ import _git_rev
        rev = _git_rev()
        # On this checkout it should return a hash
        self.assertIsNotNone(rev)
        self.assertTrue(len(rev) >= 7)


if __name__ == "__main__":
    unittest.main()
