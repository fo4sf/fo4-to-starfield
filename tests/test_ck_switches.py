"""ck_switches: string scan on a synthetic binary."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ck_switches", ROOT / "scripts/research/ck_switches.py")
ck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ck)


class CkSwitchesTest(unittest.TestCase):
    def test_scan(self):
        data = (b"\x00\x01-GenerateLips:\x00junk\xff" + "-CompileScripts".encode("utf-16le") + b"\x00\x00"
                + b"NothingHere\x00")
        found = ck.strings(data)
        self.assertEqual(ck.matches(found, ck.DEFAULT), ["-CompileScripts", "-GenerateLips:"])
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "ck.exe")
            open(p, "wb").write(data)
            self.assertEqual(ck.main([p, "--pattern", "lips"]), 0)


if __name__ == "__main__":
    unittest.main()
