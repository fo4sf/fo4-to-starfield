"""Recorded restore (src/fo4sf/launcher/restore.py) against a synthetic Starfield folder and Plugins.txt, driving the
real exp_install.py installer; nothing touches a game."""
import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from fo4sf.launcher import restore  # noqa: E402

EXP = os.path.join(ROOT, "scripts", "game", "exp_install.py")


def tes4(masters=()):
    subs = b"HEDR" + struct.pack("<H", 12) + struct.pack("<fII", 0.96, 0, 0x800)
    for m in masters:
        n = m.encode() + b"\0"
        subs += b"MAST" + struct.pack("<H", len(n)) + n + b"DATA" + struct.pack("<H", 8) + b"\0" * 8
    return b"TES4" + struct.pack("<IIIIHH", len(subs), 1, 0, 0, 0, 0) + subs


class RestoreTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        self.game = os.path.join(self.root, "Starfield")
        self.data = os.path.join(self.game, "Data")
        self.local = os.path.join(self.root, "local")
        os.makedirs(self.data)
        os.makedirs(os.path.join(self.local, "Starfield"))
        self.pt = os.path.join(self.local, "Starfield", "Plugins.txt")
        with open(self.pt, "wb") as f:
            f.write(b"# owner's comment\r\n*SomeOwnerMod.esm\r\n")
        for n, b in (("Starfield.esm", tes4()), ("SomeOwnerMod.esm", tes4(["Starfield.esm"])),
                     ("Starfield - Textures01.ba2", b"BTDX" + b"\0" * 40)):
            with open(os.path.join(self.data, n), "wb") as f:
                f.write(b)
        self.exp = os.path.join(self.root, "staging", "exp1")
        os.makedirs(os.path.join(self.exp, "Data", "Terrain"))
        with open(os.path.join(self.exp, "FO4SFExpTest.esm"), "wb") as f:
            f.write(tes4(["Starfield.esm"]))
        with open(os.path.join(self.exp, "Data", "Terrain", "x.btd"), "wb") as f:
            f.write(b"BTDB" + b"\0" * 16)
        self.env = dict(os.environ, LOCALAPPDATA=self.local)

    def exp_install(self, *args):
        r = subprocess.run([sys.executable, EXP, *args, "--starfield", self.game], env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def snap(self):
        return restore.take(self.game, self.pt)

    def apply(self, target, **kw):
        kw.setdefault("running", lambda: False)
        kw.setdefault("echo", lambda *_: None)
        return restore.apply(target, ROOT, **kw)

    def read_pt(self):
        with open(self.pt, "rb") as f:
            return f.read()

    def test_snapshot_is_read_only_and_records_plugins_txt(self):
        before = self.read_pt()
        s = self.snap()
        self.assertEqual(self.read_pt(), before)
        self.assertIsNone(s["records"]["experiment"])
        self.assertIn("sha256", s["data_top"]["SomeOwnerMod.esm"])
        self.assertNotIn("sha256", s["data_top"]["Starfield - Textures01.ba2"])

    def test_restore_removes_an_experiment_installed_since(self):
        target = self.snap()
        original = self.read_pt()
        self.exp_install("install", "--exp-dir", self.exp)
        self.assertNotEqual(self.read_pt(), original)
        p = restore.plan(target, self.snap(), ROOT)
        self.assertEqual([s["what"] for s in p["steps"]], ["uninstall experiment"])
        self.assertEqual(p["conflicts"], [])
        self.assertEqual(self.apply(target), [])
        self.assertEqual(self.read_pt(), original)                      # byte for byte, CRLF and comment kept
        self.assertFalse(os.path.exists(os.path.join(self.data, "FO4SFExpTest.esm")))
        self.assertFalse(os.path.exists(os.path.join(self.data, "Terrain", "x.btd")))

    def test_restore_reinstalls_the_recorded_experiment(self):
        self.exp_install("install", "--exp-dir", self.exp)
        target = self.snap()
        self.exp_install("uninstall")
        p = restore.plan(target, self.snap(), ROOT)
        self.assertEqual([s["what"] for s in p["steps"]], ["install experiment", "order experiment plugins"])
        self.assertEqual(self.apply(target), [])
        self.assertTrue(os.path.exists(os.path.join(self.data, "FO4SFExpTest.esm")))

    def test_owner_edit_to_plugins_txt_is_a_conflict_and_nothing_changes(self):
        target = self.snap()
        self.exp_install("install", "--exp-dir", self.exp)
        with open(self.pt, "ab") as f:
            f.write(b"*AnotherOwnerMod.esm\r\n")
        before = self.read_pt()
        p = restore.plan(target, self.snap(), ROOT)
        self.assertTrue(any("Plugins.txt" in c for c in p["conflicts"]))
        with self.assertRaises(restore.RestoreRefused):
            self.apply(target)
        self.assertEqual(self.read_pt(), before)
        self.assertTrue(os.path.exists(os.path.join(self.data, "FO4SFExpTest.esm")))

    def test_refuses_while_the_game_runs(self):
        target = self.snap()
        self.exp_install("install", "--exp-dir", self.exp)
        with self.assertRaisesRegex(restore.RestoreRefused, "running"):
            self.apply(target, running=lambda: True)
        self.assertTrue(os.path.exists(os.path.join(self.data, "FO4SFExpTest.esm")))

    def test_unowned_new_file_is_left_alone(self):
        target = self.snap()
        stray = os.path.join(self.data, "Stranger.esp")
        with open(stray, "wb") as f:
            f.write(tes4())
        p = restore.plan(target, self.snap(), ROOT)
        self.assertEqual(p["steps"], [])
        self.assertTrue(any("Stranger.esp" in n for n in p["notes"]))
        left = self.apply(target)
        self.assertTrue(os.path.exists(stray))
        self.assertEqual(left, ["Data/Stranger.esp differs"])           # reported, never deleted

    def test_changed_installed_file_is_refused_even_with_an_equal_record(self):
        # plugin already active: the install ends complete with no Plugins.txt restoration pending (review case 1)
        with open(self.pt, "ab") as f:
            f.write(b"*FO4SFExpTest.esm\r\n")
        self.exp_install("install", "--exp-dir", self.exp)
        rec = self.snap()["records"]["experiment"]
        self.assertTrue(rec["complete"])
        self.assertFalse(rec["plugins_restore_pending"])
        target = self.snap()
        for rel in ("FO4SFExpTest.esm", os.path.join("Terrain", "x.btd")):     # a plugin, then a loose file
            with self.subTest(rel=rel):
                path = os.path.join(self.data, rel)
                with open(path, "rb") as f:
                    good = f.read()
                with open(path, "wb") as f:
                    f.write(good[:-1] + b"X")
                p = restore.plan(target, self.snap(), ROOT)
                self.assertTrue(any("changed since it was installed" in c for c in p["conflicts"]), p)
                with self.assertRaises(restore.RestoreRefused):
                    self.apply(target)
                os.remove(path)
                p = restore.plan(target, self.snap(), ROOT)
                self.assertTrue(any("missing" in c for c in p["conflicts"]), p)
                with open(path, "wb") as f:
                    f.write(good)
        self.assertEqual(restore.plan(target, self.snap(), ROOT)["conflicts"], [])
        self.assertEqual(self.apply(target), [])

    def test_unhashed_archive_rewritten_at_the_same_length_is_caught_by_time(self):
        target = self.snap()
        path = os.path.join(self.data, "Starfield - Textures01.ba2")
        st = os.stat(path)
        with open(path, "wb") as f:
            f.write(b"BTDX" + b"\1" * 40)                                    # same length, new bytes
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 9))
        p = restore.plan(target, self.snap(), ROOT)
        self.assertTrue(any("Textures01" in c for c in p["conflicts"]), p)
        with self.assertRaises(restore.RestoreRefused):
            self.apply(target)
        with open(path, "wb") as f:                                           # contrast: a size change
            f.write(b"BTDX" + b"\0" * 41)
        self.assertTrue(any("Textures01" in c for c in restore.plan(target, self.snap(), ROOT)["conflicts"]))

    def test_healthy_install_with_pending_restoration_is_left_alone(self):
        self.exp_install("install", "--exp-dir", self.exp)                  # activation changed Plugins.txt
        rec = self.snap()["records"]["experiment"]
        self.assertTrue(rec["complete"])
        self.assertTrue(rec["plugins_restore_pending"])                     # owns the later uninstall's restoration
        target = self.snap()
        p = restore.plan(target, self.snap(), ROOT)
        self.assertEqual((p["steps"], p["conflicts"]), ([], []))

        def no_installer(*_a, **_k):
            raise AssertionError("no installer may run for a no-op restore")
        self.assertEqual(self.apply(target, run=no_installer), [])
        self.assertTrue(self.snap()["records"]["experiment"]["plugins_restore_pending"])

    def test_target_taken_over_a_changed_owned_file_is_refused(self):
        # review case 4: a snapshot captured while an owned file was changed or gone must not count as restored
        # once the healthy file is back
        self.exp_install("install", "--exp-dir", self.exp)
        for rel, change in (("FO4SFExpTest.esm", "edit"), (os.path.join("Terrain", "x.btd"), "edit"),
                            ("FO4SFExpTest.esm", "remove")):
            with self.subTest(rel=rel, change=change):
                path = os.path.join(self.data, rel)
                with open(path, "rb") as f:
                    good = f.read()
                if change == "edit":
                    with open(path, "wb") as f:
                        f.write(good[:-1] + b"X")
                else:
                    os.remove(path)
                target = self.snap()
                self.assertTrue(restore.owned_problems(target))
                with open(path, "wb") as f:
                    f.write(good)
                healthy = self.snap()
                p = restore.plan(target, healthy, ROOT)
                self.assertTrue(any(c.startswith("snapshot: experiment:") for c in p["conflicts"]), p)
                self.assertTrue(any(d.startswith("snapshot: experiment:") for d in restore.verify(target, healthy)))

                def no_installer(*_a, **_k):
                    raise AssertionError("no installer may run for a refused restore")
                with self.assertRaises(restore.RestoreRefused):
                    self.apply(target, run=no_installer)
                with open(path, "rb") as f:
                    self.assertEqual(f.read(), good)                   # current bytes kept
                self.assertTrue(self.snap()["records"]["experiment"]["complete"])

    def test_unhashed_owned_file_is_checked_against_the_snapshot_bytes(self):
        snap = self.snap()
        rec = {"files": ["FO4Port.esm"], "artifacts": {}}           # a port record that keeps no hash for its plugin
        target = dict(snap, records=dict(snap["records"], port=rec), owned_live={"port": {"FO4Port.esm": "a" * 64}})
        after = dict(target, owned_live={"port": {"FO4Port.esm": "b" * 64}})
        self.assertIn("port: Data/FO4Port.esm differs from the snapshot", restore.verify(target, after))
        self.assertEqual(restore.verify(target, dict(after, owned_live=target["owned_live"])), [])

    def test_vanished_unowned_file_is_a_conflict(self):
        target = self.snap()
        os.remove(os.path.join(self.data, "SomeOwnerMod.esm"))
        p = restore.plan(target, self.snap(), ROOT)
        self.assertTrue(any("SomeOwnerMod.esm" in c for c in p["conflicts"]))

    def test_port_without_staging_is_a_conflict(self):
        target = self.snap()
        target["records"]["port"] = {"files": ["FO4Port.esm"], "complete": True}
        p = restore.plan(target, self.snap(), ROOT)
        self.assertTrue(any("--port-staging" in c for c in p["conflicts"]))
        p = restore.plan(target, self.snap(), ROOT, port_staging=os.path.join(self.root, "port"))
        self.assertEqual([s["what"] for s in p["steps"]], ["install port"])

    def test_swap_order_matches_the_swap_scripts(self):
        cur = self.snap()
        cur["records"]["bridge"] = {"source_sha256": "b", "dir": "x", "plugin": "FO4SFBridge.esm"}
        cur["records"]["experiment"] = {"exp_dir": self.exp, "plugins": ["A.esm"]}
        target = self.snap()
        target["records"]["bridge"] = {"source_sha256": "c", "dir": "y", "plugin": "FO4SFBridge.esm"}
        target["records"]["experiment"] = {"exp_dir": self.exp, "plugins": ["B.esm"], "pack": True,
                                           "source_inputs": {"plugin/B.esm": "1"}}
        p = restore.plan(target, cur, ROOT)
        self.assertEqual([s["what"] for s in p["steps"]],
                         ["uninstall bridge", "uninstall experiment", "install experiment",
                          "order experiment plugins", "install bridge"])
        self.assertIn("--pack", p["steps"][2]["argv"])

    def test_cli_dry_run(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("launcher_cli", os.path.join(ROOT, "scripts", "launcher.py"))
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        snap = os.path.join(self.root, "snap.json")
        self.assertEqual(cli.main(["snapshot", "--starfield", self.game, "--out", snap, "--plugins-txt", self.pt]), 0)
        self.exp_install("install", "--exp-dir", self.exp)
        before = self.read_pt()
        self.assertEqual(cli.main(["restore", "--snapshot", snap]), 0)
        self.assertEqual(self.read_pt(), before)                        # dry run by default


if __name__ == "__main__":
    unittest.main()
