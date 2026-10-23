"""Test environment summary in fo4sf status."""
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.__main__ import _git_rev


class TestStatusEnv(unittest.TestCase):
    def test_git_rev_returns_hash_or_none(self):
        rev = _git_rev()
        # In a checkout it returns a short hash; elsewhere None is fine
        if rev is not None:
            self.assertTrue(len(rev) >= 7)
            self.assertTrue(all(c in "0123456789abcdef" for c in rev))


if __name__ == "__main__":
    unittest.main()
