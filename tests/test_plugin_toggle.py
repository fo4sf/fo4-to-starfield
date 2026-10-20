"""scripts/game/plugin_toggle.py and how exp_install.py / bridge_install.py respect it. Synthetic game folder and
Plugins.txt; never a live install."""
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "game"))
import plugin_toggle as pt  # noqa: E402
import exp_install as exp  # noqa: E402
import bridge_install as bi  # noqa: E402


def tes4(*masters):
    sub = b"".join(b"MAST" + struct.pack("<H", len(m) + 1) + m.encode() + b"\0" for m in masters)
    return b"TES4" + struct.pack("<I", len(sub)) + bytes(16) + sub


class ToggleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.game, self.data = root / "game", root / "game" / "Data"
        self.data.mkdir(parents=True)
        (root / "local" / "Starfield").mkdir(parents=True)
        self.txt = root / "local" / "Starfield" / "Plugins.txt"
        env = patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")})
        env.start()
        self.addCleanup(env.stop)
        (self.data / "Core.esm").write_bytes(tes4("FO4Port.esm"))
        (self.data / "Mission.esm").write_bytes(tes4("Core.esm"))
        (self.data / bi.PLUGIN).write_bytes(tes4())
        (self.data / exp.RECORD).write_text(json.dumps({"complete": True, "plugins": ["Core.esm", "Mission.esm"],
                                                       "files": {}, "plugins_txt": str(self.txt)}))
        (self.data / bi.ARCHIVE).write_bytes(b"BTDX")
        (self.data / bi.RECORD).write_text(json.dumps({
            "complete": True, "plugins_txt": str(self.txt),
            "files": {n: exp.digest(str(self.data / n)) for n in (bi.PLUGIN, bi.ARCHIVE)}}))
        self.original = "# keep\r\n*FO4Port.esm\r\n*Core.esm\r\n*Mission.esm\r\n*FO4SFBridge.esm\r\n"
        self.txt.write_bytes(self.original.encode())

    def run_cmd(self, *argv):
        with redirect_stdout(io.StringIO()) as buf:
            pt.main([*argv, "--starfield", str(self.game)])
        return buf.getvalue()

    def lines(self):
        return self.txt.read_bytes().decode().split("\r\n")[:-1]

    def a(self):
        return SimpleNamespace(starfield=str(self.game))

    def test_off_and_on_round_trip_byte_for_byte(self):
        self.run_cmd("off", "--plugins", "Mission.esm,FO4SFBridge.esm", "--why", "crash split")
        self.assertEqual(self.lines(), ["# keep", "*FO4Port.esm", "*Core.esm", "Mission.esm", "FO4SFBridge.esm"])
        rec = json.loads((self.data / exp.TOGGLE).read_text())
        self.assertEqual((rec["off"], rec["why"]), (["Mission.esm", "FO4SFBridge.esm"], "crash split"))
        self.assertIn("already held off", self.run_cmd("off", "--plugins", "Mission.esm"))
        self.run_cmd("on", "--plugins", "FO4SFBridge.esm")
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], ["Mission.esm"])
        self.run_cmd("on")
        self.assertEqual(self.txt.read_bytes().decode(), self.original)
        self.assertEqual(json.loads((self.data / exp.TOGGLE).read_text())["off"], [])
        self.assertIn("nothing held off", self.run_cmd("on"))

    def test_off_refusals_change_nothing(self):
        for plugins, why in (("FO4Port.esm", "not a plugin our installers own"),
                             ("Core.esm", "Mission.esm stays active and needs Core.esm"),
                             ("", "off needs --plugins")):
            with self.subTest(plugins=plugins), self.assertRaises(SystemExit) as cm:
                self.run_cmd("off", "--plugins", plugins)
            self.assertIn(why, str(cm.exception))
        self.txt.write_bytes(self.original.replace("*Mission.esm", "Mission.esm").encode())
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("off", "--plugins", "Mission.esm")
        self.assertIn("missing, inactive or duplicated", str(cm.exception))
        self.assertFalse((self.data / exp.TOGGLE).exists())
        self.txt.write_bytes(self.original.encode())
        self.run_cmd("off", "--plugins", "Core.esm,Mission.esm")       # both together: nothing left needing Core
        self.assertEqual(self.lines()[2:4], ["Core.esm", "Mission.esm"])

    def test_installers_respect_the_toggle(self):
        self.run_cmd("off", "--plugins", "Mission.esm,FO4SFBridge.esm")
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(self.a()), 0)
        self.assertIn("held off: Mission.esm", buf.getvalue())
        with redirect_stdout(io.StringIO()):
            bi.order(SimpleNamespace(starfield=str(self.game), dir=""))    # never re-ticks a held bridge
        self.assertEqual(self.lines()[4], "FO4SFBridge.esm")
        for call, what in ((lambda: exp.uninstall(self.a()), "experiment not uninstalled"),
                           (lambda: bi.uninstall(self.a()), "bridge not uninstalled")):
            with self.subTest(what=what), self.assertRaises(SystemExit) as cm:
                call()
            self.assertIn(what, str(cm.exception))
            self.assertIn("plugin_toggle.py on", str(cm.exception))
        (self.data / bi.RECORD).rename(self.data / "bridge.json.bak")      # a NEW bridge install refuses too
        with patch.object(bi, "staged", return_value=("d", "p", "x")), patch.object(bi, "source_inventory", return_value={}), \
                self.assertRaises(SystemExit) as cm:
            bi.install(SimpleNamespace(starfield=str(self.game), dir="d"))
        self.assertIn("bridge not installed: plugins held off", str(cm.exception))
        (self.data / "bridge.json.bak").rename(self.data / bi.RECORD)
        self.txt.write_bytes(self.original.encode())                      # the game re-ticked a held plugin
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(self.a()), 8)
        self.assertIn("held off by plugin_toggle.py but active", buf.getvalue())

    def test_a_relaunch_of_the_same_experiment_keeps_held_plugins_off(self):
        self.run_cmd("off", "--plugins", "Mission.esm")
        rec = {"files": {}, "source_inputs": {"k": 1}}
        a = SimpleNamespace(starfield=str(self.game), exp_dir="x")
        with patch.object(exp, "source_inventory", return_value={"k": 1}):
            exp.verify_relaunch(a, str(self.data), ["Core.esm", "Mission.esm"], False, rec, exp.held_off(str(self.data)))
            with self.assertRaisesRegex(SystemExit, "inactive"):         # without the toggle it is a fault
                exp.verify_relaunch(a, str(self.data), ["Core.esm", "Mission.esm"], False, rec)

    def test_on_refuses_a_child_whose_master_stays_held(self):
        # Codex on #407: on --plugins Mission.esm after holding Core and Mission activated Mission without its master
        self.run_cmd("off", "--plugins", "Core.esm,Mission.esm")
        before, rec = self.txt.read_bytes(), (self.data / exp.TOGGLE).read_bytes()
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("on", "--plugins", "Mission.esm")
        self.assertIn("Mission.esm needs Core.esm as a master, which stays held off", str(cm.exception))
        self.assertEqual((self.txt.read_bytes(), (self.data / exp.TOGGLE).read_bytes()), (before, rec))
        self.run_cmd("on", "--plugins", "Core.esm")                        # the master alone is fine
        self.run_cmd("on")
        self.assertEqual(self.txt.read_bytes().decode(), self.original)

    def test_a_held_bridge_ticked_again_is_refused_not_accepted(self):
        # Codex on #407: order and active accepted the record alone while *FO4SFBridge.esm was active again
        self.run_cmd("off", "--plugins", "FO4SFBridge.esm")
        self.txt.write_bytes(self.original.encode())
        with self.assertRaisesRegex(ValueError, "held off by plugin_toggle.py but active"):
            bi.order(SimpleNamespace(starfield=str(self.game), dir=""))
        with redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(exp.active(self.a()), 8)
        self.assertIn("but active in Plugins.txt: fo4sfbridge.esm", buf.getvalue())
        self.assertEqual(self.txt.read_bytes().decode(), self.original)       # nothing rewritten

    def test_order_skips_held_plugins(self):
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes("*Core.esm\r\n*FO4Port.esm\r\nMission.esm\r\n".encode())   # Core before its master
        with redirect_stdout(io.StringIO()) as buf, patch.object(exp, "require_complete_master"):
            self.assertEqual(exp.order(self.a()), 0)
        self.assertIn("held off (plugin_toggle.py), left unticked: Mission.esm", buf.getvalue())
        self.assertEqual(self.lines(), ["*FO4Port.esm", "*Core.esm", "Mission.esm"])

    def test_a_bad_record_and_a_lost_line(self):
        (self.data / exp.TOGGLE).write_text(json.dumps({"off": "Mission.esm"}))
        with self.assertRaises(SystemExit):
            self.run_cmd("status")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(exp.active(self.a()), 8)
        (self.data / exp.TOGGLE).unlink()
        self.run_cmd("off", "--plugins", "Mission.esm")
        self.txt.write_bytes("*FO4Port.esm\r\n*Core.esm\r\n".encode())
        with self.assertRaises(SystemExit) as cm:
            self.run_cmd("on")
        self.assertIn("no Plugins.txt line left for Mission.esm", str(cm.exception))
        self.assertEqual(json.loads(self.run_cmd("status"))["off"], ["Mission.esm"])


if __name__ == "__main__":
    unittest.main()
