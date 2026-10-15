"""bridge_log.py: the observation bridge's log lines (synthetic; the real log is written by FO4SF_Bridge.psc)."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "game"))
import bridge_log  # noqa: E402

FULL = "FO4SF rt=12.845 pos=-2189.263428 -1553.490112 105.260002 ang=181.914001 cell=33556480 world=50331649 loaded=True cmd=7 n=12"


class ParseTests(unittest.TestCase):
    def test_full_line(self):
        d = bridge_log.parse_line(FULL)
        self.assertEqual(d["rt"], 12.845)
        self.assertEqual(d["pos"], [-2189.263428, -1553.490112, 105.260002])
        self.assertEqual(d["ang"], 181.914001)
        self.assertEqual(d["cell"], "02000800")                 # decimal 33556480 printed back as hex
        self.assertEqual(d["world"], "03000001")
        self.assertTrue(d["loaded"])
        self.assertEqual(d["cmd"], 7)
        self.assertEqual(d["n"], 12)

    def test_optional_fields_and_none(self):
        d = bridge_log.parse_line("FO4SF rt=3.0 pos=1 2 3 ang=0 cell=none world=none loaded=False n=1")
        self.assertIsNone(d["cell"])
        self.assertIsNone(d["world"])
        self.assertFalse(d["loaded"])
        self.assertNotIn("cmd", d)
        d = bridge_log.parse_line("FO4SF rt=3.5 pos=1 2 3")
        self.assertEqual(d["pos"], [1.0, 2.0, 3.0])
        self.assertNotIn("ang", d)

    def test_other_lines_ignored(self):
        for s in ("FO4SF init rt=0.5", "", "[10/14/2026 - 09:12:03PM] warning: Property x not found",
                  "FO4SF rt=1 pos=1 2", "FO4SF rt=1 pos=a b c", "FO4SF rt=1 pos=1 2 3 cmd=x"):
            self.assertIsNone(bridge_log.parse_line(s), s)

    def test_negative_cmd_and_int_bool(self):
        d = bridge_log.parse_line("FO4SF rt=1 pos=0 0 0 loaded=1 cmd=-1")
        self.assertTrue(d["loaded"])
        self.assertEqual(d["cmd"], -1)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.log = os.path.join(self.dir.name, "fo4sf.0.log")

    def tearDown(self):
        self.dir.cleanup()

    def write(self, *lines):
        with open(self.log, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def test_missing_log(self):
        r = bridge_log.latest(self.log)
        self.assertFalse(r["ok"])
        self.assertEqual(bridge_log.read_lines(self.log), [])

    def test_latest_and_stale(self):
        self.write("FO4SF init rt=0.5", "FO4SF rt=1.0 pos=1 2 3 n=1", FULL)
        r = bridge_log.latest(self.log, max_age=60)
        self.assertTrue(r["ok"])
        self.assertEqual(r["n"], 12)
        old = time.time() - 120
        os.utime(self.log, (old, old))
        r = bridge_log.latest(self.log, max_age=60)
        self.assertFalse(r["ok"])
        self.assertIn("old", r["why"])
        self.assertEqual(r["last"]["n"], 12)                  # the stale line is still reported, never as ok

    def test_wait_cmd_respects_since_n(self):
        self.write("FO4SF rt=1 pos=0 0 0 cmd=7 n=1", "FO4SF rt=2 pos=0 0 0 n=2")
        self.assertIsNone(bridge_log.wait_cmd(self.log, 7, timeout=0.3, since_n=1))   # the old echo does not count
        self.assertEqual(bridge_log.wait_cmd(self.log, 7, timeout=0.3)["n"], 1)
        self.assertIsNone(bridge_log.wait_cmd(self.log, 8, timeout=0.3))

    def test_wait_move(self):
        import threading
        self.write("FO4SF rt=1 pos=0 0 0 n=1")
        first, moved = bridge_log.wait_move(self.log, min_m=0.5, timeout=0.3)
        self.assertEqual(first["pos"], [0.0, 0.0, 0.0])
        self.assertIsNone(moved)                              # nothing moved: the same line all along
        # the game appends lines while the runner waits: a 0.3 m step is not a move, the 0.6 m one is
        def later():
            with open(self.log, "a", encoding="utf-8") as f:
                f.write("FO4SF rt=2 pos=0.3 0 0 n=2\nFO4SF rt=3 pos=0.6 0 0 n=3\n")
        threading.Timer(0.15, later).start()
        first, moved = bridge_log.wait_move(self.log, min_m=0.5, timeout=2.0)
        self.assertEqual(first["n"], 1)
        self.assertEqual(moved["n"], 3)

    def test_cli_latest(self):
        self.write(FULL)
        import io
        import json
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = bridge_log.main(["latest", "--log", self.log, "--max-age", "60"])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["cmd"], 7)


if __name__ == "__main__":
    unittest.main()
