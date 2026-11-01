"""Recorded restore of a port and an experiment whose plugin masters FO4Port.esm (a slice door plugin): exp_install.py
order refuses a plugin whose master is not active, so the order step runs after the port is back. The real
exp_install.py and deploy_starfield.py --restore-stdin run on a synthetic Starfield folder (no Archive2); no game."""
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import restore  # noqa: E402


def tes4(masters=()):
    subs = b"HEDR" + struct.pack("<H", 12) + struct.pack("<fII", 0.96, 0, 0x800)
    for m in masters:
        n = m.encode() + b"\0"
        subs += b"MAST" + struct.pack("<H", len(n)) + n + b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    return b"TES4" + struct.pack("<IIIIHH", len(subs), 1, 0, 0, 0, 0) + subs


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class PortMasterOrderTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        d = t.name
        self.game, self.local = os.path.join(d, "Starfield"), os.path.join(d, "local")
        self.pt = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.pt, b"*SomeOwnerMod.esm\r\n")
        write(os.path.join(self.game, "Data", "Starfield.esm"), tes4())
        write(os.path.join(self.game, "Data", "SomeOwnerMod.esm"), tes4(["Starfield.esm"]))
        self.stage = os.path.join(d, "port_stage")                       # a prebuilt port: plugin and main archive
        write(os.path.join(self.stage, "FO4Port.esm"), tes4(["Starfield.esm"]))
        write(os.path.join(self.stage, "FO4Port - Main.ba2"), b"BTDX" + b"\0" * 40)
        self.exp = os.path.join(d, "exp_slice")
        write(os.path.join(self.exp, "FO4SliceDoor.esm"), tes4(["Starfield.esm", "FO4Port.esm"]))
        self.env = dict(os.environ, LOCALAPPDATA=self.local)
        local = mock.patch.dict(os.environ, {"LOCALAPPDATA": self.local})
        local.start()
        self.addCleanup(local.stop)

    def run_tool(self, *argv, stdin=None):
        r = subprocess.run([sys.executable, *argv, "--starfield", self.game], input=stdin, text=True,
                           capture_output=True, env=self.env, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def identity(self, name):
        with open(os.path.join(self.stage, name), "rb") as f:
            b = f.read()
        return {"size": len(b), "sha256": hashlib.sha256(b).hexdigest()}

    def test_the_slice_experiment_and_the_port_come_back_from_vanilla(self):
        vanilla = restore.take(self.game, self.pt)
        spec = {"schema": 1, "files": ["FO4Port.esm", "FO4Port - Main.ba2"], "core_sha256": None,
                "artifacts": {n: self.identity(n) for n in ("FO4Port.esm", "FO4Port - Main.ba2")}}
        self.run_tool(os.path.join("scripts", "deploy_starfield.py"), "install", "--staging", self.stage,
                      "--restore-stdin", stdin=json.dumps(spec))
        self.run_tool(os.path.join("scripts", "game", "exp_install.py"), "install", "--exp-dir", self.exp)
        target = restore.take(self.game, self.pt)
        self.assertEqual(restore.apply(vanilla, ROOT, running=lambda: False, echo=lambda *_: None), [])
        p = restore.plan(target, restore.take(self.game, self.pt), ROOT, port_staging=self.stage)
        self.assertEqual(p["conflicts"], [])
        self.assertEqual([s["what"] for s in p["steps"]],
                         ["install experiment", "install port", "order experiment plugins"])
        self.assertEqual(restore.apply(target, ROOT, port_staging=self.stage, running=lambda: False,
                                       echo=lambda *_: None), [])
        for n in ("FO4Port.esm", "FO4SliceDoor.esm"):
            self.assertTrue(os.path.isfile(os.path.join(self.game, "Data", n)), n)

    def test_without_a_port_change_order_still_follows_the_experiment(self):
        snap = restore.take(self.game, self.pt)
        target = dict(snap, records=dict(snap["records"], experiment={"exp_dir": self.exp, "plugins": ["X.esm"]}))
        p = restore.plan(target, snap, ROOT)
        self.assertEqual([s["what"] for s in p["steps"]], ["install experiment", "order experiment plugins"])


if __name__ == "__main__":
    unittest.main()
