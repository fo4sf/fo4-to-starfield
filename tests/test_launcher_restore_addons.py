"""Recorded restore (src/fo4sf/launcher/restore.py) with the installers beyond the port, the experiment and the bridge:
the map markers plugin, the planet, quest and combined probes. A synthetic Starfield folder and Plugins.txt; the real
exp_install.py and map_markers_install.py run, the archive builder replaced by a stub (no game, no Archive2)."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
from ba2_fixture import archive_from_tree  # noqa: E402
from fo4sf.launcher import bundle, restore  # noqa: E402
import exp_install  # noqa: E402
import map_markers_install as mm  # noqa: E402

EXP = os.path.join(ROOT, "scripts", "game", "exp_install.py")
CORE = "FO4TerrainCore.esm"


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


class AddonRestoreTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = t.name
        self.game = os.path.join(self.root, "Starfield")
        self.data = os.path.join(self.game, "Data")
        self.local = os.path.join(self.root, "local")
        self.pt = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.pt, b"# owner's comment\r\n*SomeOwnerMod.esm\r\n")
        write(os.path.join(self.data, "Starfield.esm"), tes4())
        write(os.path.join(self.data, "SomeOwnerMod.esm"), tes4(["Starfield.esm"]))
        self.exp = os.path.join(self.root, "staging", "core")                  # the core, installed as the experiment
        write(os.path.join(self.exp, CORE), tes4(["Starfield.esm"]))
        write(os.path.join(self.exp, "Data", "Terrain", "x.btd"), b"BTDB" + b"\0" * 16)
        self.markers = os.path.join(self.root, "staging", "mapmarkers")          # staged against that core
        write(os.path.join(self.markers, mm.PLUGIN), tes4([CORE]))
        write(os.path.join(self.markers, mm.PEX), b"pex")
        write(os.path.join(self.markers, mm.PIN), json.dumps(
            {"masters": {CORE: exp_install.digest(os.path.join(self.exp, CORE))}}).encode())
        self.env = dict(os.environ, LOCALAPPDATA=self.local)
        old_build = exp_install.build_ba2

        def stub_build(_a, root_dir, out):
            write(out, archive_from_tree(Path(root_dir)))
            return out
        exp_install.build_ba2 = stub_build
        self.addCleanup(setattr, exp_install, "build_ba2", old_build)

    # --- the real installers -------------------------------------------------------------------------------------
    def exp_install(self, *args):
        r = subprocess.run([sys.executable, EXP, *args, "--starfield", self.game], env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def markers_install(self, *args):
        """map_markers_install.py in this process, so the archive builder is the stub."""
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": self.local}):
            mm.main(list(args))

    def run_step(self, argv, cwd=None, env=None):
        """restore.apply's runner: a map markers install in this process (Archive2 stubbed), the rest for real."""
        if os.path.basename(argv[1]) == "map_markers_install.py" and argv[2] == "install":
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": env["LOCALAPPDATA"]}):
                try:
                    mm.main(argv[2:])
                except SystemExit as e:
                    return SimpleNamespace(returncode=1 if e.code else 0)
            return SimpleNamespace(returncode=0)
        return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True)

    def snap(self):
        return restore.take(self.game, self.pt)

    def apply(self, target):
        return restore.apply(target, ROOT, running=lambda: False, echo=lambda *_: None, run=self.run_step)

    def read_pt(self):
        with open(self.pt, "rb") as f:
            return f.read()

    def install_core_and_markers(self):
        self.exp_install("install", "--exp-dir", self.exp)
        self.markers_install("install", "--dir", self.markers, "--starfield", self.game)
        self.assertIn("*FO4SFMapMarkers.esm", self.read_pt().decode())

    # --- end to end ----------------------------------------------------------------------------------------------
    def test_a_vanilla_restore_takes_the_map_markers_off_first(self):
        # the owner's 31 Oct plan: "a launcher switch back to vanilla would be refused, because the markers plugin
        # counts as a conflict" (its Plugins.txt line was no installer's, so it read as the owner's edit)
        vanilla, original = self.snap(), self.read_pt()
        self.install_core_and_markers()
        p = restore.plan(vanilla, self.snap(), ROOT)
        self.assertEqual(p["conflicts"], [])
        self.assertEqual([s["what"] for s in p["steps"]], ["uninstall markers", "uninstall experiment"])
        self.assertEqual(p["plugins_txt"], "restore")
        self.assertEqual(self.apply(vanilla), [])
        self.assertEqual(self.read_pt(), original)                              # byte for byte
        for name in (mm.PLUGIN, mm.ARCHIVE, mm.RECORD, CORE):
            self.assertFalse(os.path.exists(os.path.join(self.data, name)), name)

    def test_a_restore_puts_the_core_and_then_the_markers_back(self):
        self.install_core_and_markers()
        target = self.snap()
        self.markers_install("uninstall", "--starfield", self.game)
        self.exp_install("uninstall")
        p = restore.plan(target, self.snap(), ROOT)
        self.assertEqual(p["conflicts"], [])
        self.assertEqual([s["what"] for s in p["steps"]],
                         ["install experiment", "order experiment plugins", "install markers"])
        self.assertEqual(self.apply(target), [])
        import base64
        self.assertEqual(self.read_pt(), base64.b64decode(target["plugins_txt_b64"]))     # byte for byte
        self.assertTrue(self.snap()["records"]["markers"]["complete"])
        self.assertTrue(os.path.exists(os.path.join(self.data, mm.PLUGIN)))

    def test_the_markers_alone_installed_since_come_off_alone(self):
        self.exp_install("install", "--exp-dir", self.exp)
        target = self.snap()
        self.markers_install("install", "--dir", self.markers, "--starfield", self.game)
        p = restore.plan(target, self.snap(), ROOT)
        self.assertEqual(([s["what"] for s in p["steps"]], p["conflicts"]), (["uninstall markers"], []))
        self.assertEqual(self.apply(target), [])
        self.assertTrue(os.path.exists(os.path.join(self.data, CORE)))

    def test_a_snapshot_from_before_the_markers_were_known(self):
        # snapshots taken before 2026-10-31 hold only the port, experiment and bridge records
        old = lambda s: dict(s, records={c: s["records"][c] for c in ("port", "experiment", "bridge")})  # noqa: E731
        vanilla, original = old(self.snap()), self.read_pt()
        self.install_core_and_markers()
        # no markers record file in Data when it was taken: they were not installed, and they come off
        p = restore.plan(vanilla, self.snap(), ROOT)
        self.assertEqual(([s["what"] for s in p["steps"]], p["conflicts"]),
                         (["uninstall markers", "uninstall experiment"], []))
        self.assertEqual(self.apply(vanilla), [])
        self.assertEqual(self.read_pt(), original)
        # taken while they were installed: their record was not kept, so nothing is planned and nothing runs
        self.install_core_and_markers()
        with_markers = old(self.snap())
        self.markers_install("uninstall", "--starfield", self.game)
        p = restore.plan(with_markers, self.snap(), ROOT)
        self.assertEqual(p["steps"], [])
        self.assertEqual(p["conflicts"], ["snapshot: taken before restore knew markers (FO4SFMapMarkers.install.json "
                                          "was in Data, its record was not kept); take a new snapshot"])
        before = self.read_pt()

        def no_installer(*_a, **_k):
            raise AssertionError("no installer may run for a refused restore")
        with self.assertRaises(restore.RestoreRefused):
            restore.apply(with_markers, ROOT, running=lambda: False, echo=lambda *_: None, run=no_installer)
        self.assertEqual(self.read_pt(), before)

    # --- the plan: riders and sources ----------------------------------------------------------------------------
    def records(self, **recs):
        """A snapshot of this folder with these records, each one's owned files present at its recorded hash."""
        s = self.snap()
        s["records"] = dict(s["records"], **recs)
        s["owned_live"] = {c: {rel: want or "f" * 64 for rel, want in restore.owned_expected(c, r).items()}
                           for c, r in s["records"].items() if r}
        return s

    def folder(self, name):
        d = os.path.join(self.root, "staging", name)
        os.makedirs(d, exist_ok=True)
        return d

    def test_a_core_swap_takes_the_markers_off_and_puts_them_back(self):
        marks = {"schema": 2, "dir": self.markers, "plugin": mm.PLUGIN, "source_sha256": "m"}
        a = {"exp_dir": self.folder("core_a"), "plugins": [CORE], "pack": True, "source_inputs": {"plugin/x": "1"}}
        b = dict(a, exp_dir=self.folder("core_b"), source_inputs={"plugin/x": "2"})
        p = restore.plan(self.records(experiment=b, markers=marks), self.records(experiment=a, markers=dict(marks)), ROOT)
        self.assertEqual(p["conflicts"], [])
        self.assertEqual([s["what"] for s in p["steps"]],
                         ["uninstall markers", "uninstall experiment", "install experiment", "order experiment plugins",
                          "install markers"])
        self.assertTrue(any(n.startswith("markers: taken off and put back around the experiment") for n in p["notes"]))
        self.assertEqual(p["steps"][-1]["argv"][2:], ["install", "--dir", self.markers, "--starfield", self.game])
        # the same core on both sides: the markers are left alone
        p = restore.plan(self.records(experiment=a, markers=marks), self.records(experiment=dict(a), markers=marks), ROOT)
        self.assertEqual(p["steps"], [])

    def test_a_rider_whose_staged_folder_is_gone_is_refused_before_anything_runs(self):
        gone = os.path.join(self.root, "staging", "gone")
        marks = {"dir": gone, "plugin": mm.PLUGIN, "source_sha256": "m"}
        a = {"exp_dir": self.folder("core_a"), "plugins": [CORE]}
        b = dict(a, exp_dir=self.folder("core_b"))
        p = restore.plan(self.records(experiment=b, markers=marks), self.records(experiment=a, markers=marks), ROOT)
        self.assertIn(f"markers: source folder {gone} is gone", p["conflicts"])
        self.assertNotIn("install markers", [s["what"] for s in p["steps"]])

    def test_a_rider_kept_while_its_base_goes_is_refused_before_anything_runs(self):
        # exp_install.py uninstall leaves the markers installed, so a snapshot can hold them without the core. Restoring
        # to it from an install with the core would take both off and then fail to put the markers back
        self.install_core_and_markers()
        self.exp_install("uninstall")
        target = self.snap()
        self.assertIsNone(target["records"]["experiment"])
        self.exp_install("install", "--exp-dir", self.exp)
        before = self.read_pt()
        p = restore.plan(target, self.snap(), ROOT)
        self.assertIn("markers: the snapshot has it without the experiment it rides on, which restore would "
                      "uninstall; its installer would refuse to put it back", p["conflicts"])

        def no_installer(*_a, **_k):
            raise AssertionError("no installer may run for a refused restore")
        with self.assertRaisesRegex(restore.RestoreRefused, "rides on"):
            restore.apply(target, ROOT, running=lambda: False, echo=lambda *_: None, run=no_installer)
        self.assertEqual(self.read_pt(), before)
        for name in (CORE, mm.PLUGIN, mm.RECORD):
            self.assertTrue(os.path.exists(os.path.join(self.data, name)), name)

    def test_a_port_staging_folder_that_is_gone_is_refused(self):
        port = {"files": ["FO4Port.esm"], "artifacts": {"FO4Port.esm": {"sha256": "1"}}}
        gone = os.path.join(self.root, "staging", "no_port")
        p = restore.plan(self.records(port=port), self.snap(), ROOT, port_staging=gone)
        self.assertIn(f"port: staging folder {gone} is gone", p["conflicts"])
        self.assertEqual(p["steps"], [])

    def test_a_plugin_toggle_hold_is_refused_before_anything_runs(self):
        # the launcher's bridge=off (or a crash split) holds plugins off through plugin_toggle.py; the installers refuse
        # to uninstall under a hold, so a restore went as far as its first such step and stopped there
        write(os.path.join(self.exp, "FO4SFExtra.esm"), tes4(["Starfield.esm"]))
        vanilla = self.snap()
        self.exp_install("install", "--exp-dir", self.exp, "--plugins", f"{CORE},FO4SFExtra.esm")
        toggle = os.path.join(ROOT, "scripts", "game", "plugin_toggle.py")
        r = subprocess.run([sys.executable, toggle, "off", "--plugins", "FO4SFExtra.esm", "--starfield", self.game],
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        held, before = self.snap(), self.read_pt()
        self.assertEqual(held["held"], ["FO4SFExtra.esm"])
        p = restore.plan(vanilla, held, ROOT)
        self.assertIn("plugin_toggle.py holds FO4SFExtra.esm off (Data/FO4SF.toggle.json): run plugin_toggle.py on "
                      "first, then restore", p["conflicts"])

        def no_installer(*_a, **_k):
            raise AssertionError("no installer may run for a refused restore")
        with self.assertRaisesRegex(restore.RestoreRefused, "plugin_toggle.py holds"):
            restore.apply(vanilla, ROOT, running=lambda: False, echo=lambda *_: None, run=no_installer)
        self.assertEqual(self.read_pt(), before)
        self.assertTrue(os.path.exists(os.path.join(self.data, "FO4SFExtra.esm")))
        r = subprocess.run([sys.executable, toggle, "on", "--starfield", self.game], env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(restore.plan(vanilla, self.snap(), ROOT)["conflicts"], [])
        self.assertEqual(self.apply(vanilla), [])                        # released: the restore goes through
        self.assertEqual(self.read_pt(), b"# owner's comment\r\n*SomeOwnerMod.esm\r\n")

    def test_a_hold_blocks_any_change_but_not_a_restore_with_nothing_to_do(self):
        combined = {"dir": self.folder("focc_probe"), "plugin": "FO4SFCombinedProbe.esm", "source_sha256": "c"}
        core = {"exp_dir": self.folder("core_a"), "plugins": [CORE]}
        now = self.records(experiment=core, combined_probe=combined)
        for held, text in ((["FO4SFBridge.esm"], "holds FO4SFBridge.esm off"), ("unreadable", "toggle.json, unreadable")):
            with self.subTest(held=held):
                p = restore.plan(self.snap(), dict(now, held=held), ROOT)   # the combined probe's uninstall would
                self.assertEqual([s["what"] for s in p["steps"]],            # run before the core's refused
                                 ["uninstall combined_probe", "uninstall experiment"])
                self.assertTrue(any(text in c for c in p["conflicts"]), p["conflicts"])
        p = restore.plan(now, dict(now, held=["FO4SFBridge.esm"]), ROOT)
        self.assertEqual((p["steps"], p["plugins_txt"], p["conflicts"]), ([], "same", []))
        self.assertEqual(restore.plan(self.snap(), dict(self.snap(), held=[]), ROOT)["conflicts"], [])

    def test_the_quest_probe_rides_on_the_port_and_the_combined_probe_on_the_core(self):
        quest = {"dir": self.folder("qprobe"), "plugin": "FO4SFQuestProbe.esm", "source_sha256": "q"}
        combined = {"dir": self.folder("focc_probe"), "plugin": "FO4SFCombinedProbe.esm", "source_sha256": "c"}
        port1 = {"files": ["FO4Port.esm"], "artifacts": {"FO4Port.esm": {"sha256": "1"}}}
        port2 = {"files": ["FO4Port.esm"], "artifacts": {"FO4Port.esm": {"sha256": "2"}}}
        core = {"exp_dir": self.folder("core_a"), "plugins": [CORE]}
        p = restore.plan(self.records(port=port2, experiment=core, quest_probe=quest, combined_probe=combined),
                         self.records(port=port1, experiment=dict(core), quest_probe=quest, combined_probe=combined),
                         ROOT, port_staging=self.folder("port"))
        self.assertEqual(p["conflicts"], [])
        self.assertEqual([s["what"] for s in p["steps"]],
                         ["uninstall quest_probe", "uninstall port", "install port", "install quest_probe"])
        self.assertTrue(p["steps"][0]["argv"][1].endswith(os.path.join("questprobe", "questprobe_install.py")))
        core_b = dict(core, exp_dir=self.folder("core_b"))
        p = restore.plan(self.records(experiment=core_b, combined_probe=combined),
                         self.records(experiment=core, combined_probe=combined), ROOT)
        self.assertEqual([s["what"] for s in p["steps"]],
                         ["uninstall combined_probe", "uninstall experiment", "install experiment",
                          "order experiment plugins", "install combined_probe"])

    def test_the_planet_probe_is_its_own_install_and_rides_on_nothing(self):
        planet = {"exp_dir": self.folder("planet_probe"), "plugins": ["FO4SFPlanet.esm", "FO4SFPlanetProbe.esm"],
                  "pack": True, "source_inputs": {"plugin/FO4SFPlanet.esm": "p"},
                  "files": {"FO4SFPlanet.esm": "a" * 64, "FO4SFPlanet - Main.ba2": "b" * 64}}
        core = {"exp_dir": self.folder("core_a"), "plugins": [CORE]}
        core_b = dict(core, exp_dir=self.folder("core_b"))
        # a core swap leaves the planet probe where it is (its plugins master Starfield.esm only)
        p = restore.plan(self.records(experiment=core_b, planet_probe=planet),
                         self.records(experiment=core, planet_probe=dict(planet)), ROOT)
        self.assertNotIn("planet_probe", " ".join(s["what"] for s in p["steps"]))
        # a planet probe installed since the snapshot comes off; one the snapshot had goes back on from its stage
        p = restore.plan(self.snap(), self.records(planet_probe=planet), ROOT)
        self.assertEqual([s["what"] for s in p["steps"]], ["uninstall planet_probe"])
        p = restore.plan(self.records(planet_probe=planet), self.snap(), ROOT)
        self.assertEqual(p["steps"][0]["argv"][2:], ["install", "--dir", planet["exp_dir"], "--starfield", self.game])
        self.assertIn("fo4sfplanet.esm", restore.owned_plugins(self.records(planet_probe=planet)))

    def test_volatile_fields_do_not_make_a_rider_another_install(self):
        a = {"dir": self.markers, "plugin": mm.PLUGIN, "source_sha256": "m", "files": {mm.PLUGIN: "1"},
             "plugins_restore_pending": True, "plugins_original": "AAAA"}
        b = dict(a, plugins_restore_pending=False, plugins_original=None, masters_sha256={CORE.casefold(): "x"})
        self.assertEqual(restore.record_identity("markers", a), restore.record_identity("markers", b))
        self.assertNotEqual(restore.record_identity("markers", a),
                            restore.record_identity("markers", dict(a, source_sha256="other")))

    def test_every_installer_record_is_known_and_its_script_exists(self):
        for comp, (rec, script) in restore.COMPONENTS.items():
            self.assertTrue(os.path.isfile(os.path.join(ROOT, script)), script)
            self.assertIn(comp, restore.INSTALL_ORDER)
            self.assertIn(rec, bundle.RECORDS)                         # the support bundle carries every record
        self.assertEqual(restore.COMPONENTS["markers"][0], mm.RECORD)
        self.assertEqual(sorted(restore.INSTALL_ORDER), sorted(restore.COMPONENTS))
        self.assertEqual(restore.INSTALL_ORDER[-2:], ("markers", "bridge"))   # cycle.ps1: markers, then the bridge
        for rider, base in restore.RIDES_ON.items():
            self.assertLess(restore.INSTALL_ORDER.index(base), restore.INSTALL_ORDER.index(rider))
        for comp in ("planet_probe", "quest_probe", "combined_probe"):
            src = Path(ROOT, restore.COMPONENTS[comp][1]).read_text(encoding="utf-8")
            self.assertIn(f'"{restore.COMPONENTS[comp][0]}"', src, comp)         # the record name the tool writes


if __name__ == "__main__":
    unittest.main()
