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

    def test_real_line_of_the_first_run(self):
        # fo4sf.0.log, 2026-10-14 21:29 (Vault111Cryo of the pinned build): the game prefixes a clock, prints six
        # decimals, "true" in lower case and "none" for no worldspace in an interior
        d = bridge_log.parse_line("[21:29:40] FO4SF rt=99.711006 pos=1.531505 -7.385632 -0.851672 ang=0.000000 "
                                  "cell=50336243 world=none loaded=true n=32")
        self.assertEqual(d["pos"], [1.531505, -7.385632, -0.851672])
        self.assertEqual(d["cell"], "030011F3")                # 50336243: FO4Port.esm (03) Vault111Cryo
        self.assertIsNone(d["world"])
        self.assertTrue(d["loaded"])
        self.assertEqual(d["n"], 32)
        self.assertIsNone(bridge_log.parse_line("[21:28:47] fo4sf log opened (PC-64)"))
        self.assertIsNone(bridge_log.parse_line("[21:28:47] FO4SF init rt=46.830002"))

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


class EventTests(unittest.TestCase):
    """The probe's lines (FO4SF_Probe.psc) and acknowledgements beside the timer's position lines."""
    def test_ack_ref_player_and_init(self):
        self.assertEqual(bridge_log.parse_event("[21:33:44] ack 7"), None)          # a bare TraceUser without the prefix word
        self.assertEqual(bridge_log.parse_event("[21:33:44] FO4SF ack probe-1"), {"kind": "ack", "tag": "probe-1"})
        self.assertEqual(bridge_log.parse_event("FO4SF ack before load"), {"kind": "ack", "tag": "before load"})
        e = bridge_log.parse_event("[21:35:00] FO4SF ref=1057678 pos=29.100000 48.100000 4.100000 ang=90.000000 "
                                   "cell=50336243 disabled=False loaded=true")
        self.assertEqual(e["kind"], "ref")
        self.assertEqual(e["id"], "0010238E")
        self.assertEqual(e["pos"], [29.1, 48.1, 4.1])
        self.assertEqual(e["cell"], "030011F3")
        self.assertFalse(e["disabled"])
        self.assertTrue(e["loaded"])
        self.assertEqual(bridge_log.parse_event("FO4SF ref=12 none"), {"kind": "ref", "id": "0000000C", "none": True})
        p = bridge_log.parse_event("[1:2:3] FO4SF player pos=1 2 3 ang=4")
        self.assertEqual((p["kind"], p["pos"], p["ang"]), ("player", [1.0, 2.0, 3.0], 4.0))
        self.assertEqual(bridge_log.parse_event("[21:28:47] FO4SF init rt=46.830002"), {"kind": "init"})
        self.assertEqual(bridge_log.parse_event(FULL)["kind"], "pos")
        self.assertIsNone(bridge_log.parse_event("[21:28:47] fo4sf log opened (PC-64)"))

    def test_events_and_wait_ack_on_a_file(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "fo4sf.0.log")
            with open(log, "w", encoding="utf-8") as f:
                f.write("[1] fo4sf log opened\n[1] FO4SF init rt=1\n" + FULL + "\n[2] FO4SF ack probe-1\n[2] FO4SF ref=5 none\n")
            kinds = [e["kind"] for e in bridge_log.read_events(log)]
            self.assertEqual(kinds, ["init", "pos", "ack", "ref"])
            self.assertTrue(bridge_log.wait_ack(log, "probe-1", timeout=0.3))
            self.assertFalse(bridge_log.wait_ack(log, "probe-2", timeout=0.3))
            import io
            import json
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = bridge_log.main(["events", "--log", log])
            self.assertEqual(rc, 0)
            self.assertEqual([json.loads(l)["kind"] for l in buf.getvalue().splitlines()], ["init", "ack", "ref"])


class ClockAgeTests(unittest.TestCase):
    """Freshness by the line's own clock stamp (bridge_probe_1015 a1: the file's mtime said fresh for a 30 s old line)."""
    def test_clock_age(self):
        now = time.mktime((2026, 10, 14, 23, 1, 5, 0, 0, -1))
        self.assertAlmostEqual(bridge_log.clock_age("23:00:37", now), 28.0, places=3)
        self.assertAlmostEqual(bridge_log.clock_age("23:01:05", now), 0.0, places=3)
        self.assertAlmostEqual(bridge_log.clock_age("23:01:04", now), 1.0, places=3)
        midnight = time.mktime((2026, 10, 15, 0, 0, 2, 0, 0, -1))
        self.assertAlmostEqual(bridge_log.clock_age("23:59:59", midnight), 3.0, places=3)
        self.assertIsNone(bridge_log.clock_age(None))
        self.assertIsNone(bridge_log.clock_age("rt=5"))

    def test_latest_uses_the_stamp_not_the_mtime(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "fo4sf.0.log")
            old = time.strftime("%H:%M:%S", time.localtime(time.time() - 40))
            with open(log, "w", encoding="utf-8") as f:
                f.write(f"[{old}] FO4SF rt=1 pos=-10.07 43.95 -10.95 n=7\n")       # the file is new, the line is not
            r = bridge_log.latest(log, max_age=3)
            self.assertFalse(r["ok"])
            self.assertIn("newest line", r["why"])
            self.assertEqual(r["last"]["n"], 7)
            now = time.strftime("%H:%M:%S")
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"[{now}] FO4SF rt=2 pos=-470.88 -2251.90 0.48 n=8\n")
            r = bridge_log.latest(log, max_age=3)
            self.assertTrue(r["ok"])
            self.assertEqual(r["n"], 8)
            self.assertEqual(r["clock"], now)


class SignedFormIdTests(unittest.TestCase):
    """bridge_probe_1015b (2026-10-14): on a planet the worldspace's form id printed negative (Papyrus signed int), the
    line did not parse, and every read saw the last Vault line as the newest one."""
    def test_planet_line_with_a_negative_world_id(self):
        d = bridge_log.parse_line("[23:31:07] FO4SF rt=217.383011 pos=-470.882690 -2251.897461 0.404062 ang=90.000000 "
                                  "cell=636176 world=-16708235 loaded=true n=26")
        self.assertIsNotNone(d)
        self.assertEqual(d["pos"], [-470.88269, -2251.897461, 0.404062])
        self.assertEqual(d["cell"], "0009B510")
        self.assertEqual(d["world"], f"{-16708235 & 0xFFFFFFFF:08X}")
        self.assertEqual(d["n"], 26)
        r = bridge_log.parse_event("FO4SF ref=-5 pos=1 2 3 cell=-16708235")
        self.assertEqual(r["cell"], f"{-16708235 & 0xFFFFFFFF:08X}")
