"""deploy_starfield.py install --batch on a synthetic interior batch stage (result.json + port\\), no game: the install set
is copied as built, each file against its pinned sha256, the texture companions are activated right after FO4Port.esm,
and uninstall takes all of it back out (docs/terrain/interior-batches.md "Install set")."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "deploy_starfield", Path(__file__).resolve().parents[1] / "scripts" / "deploy_starfield.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)

FILES = {
    "FO4Port.esm": b"TES4" + b"port" * 8,
    "FO4Port - Main.ba2": b"BTDX" + b"main" * 8,
    "FO4Port - Textures.ba2": b"BTDX" + b"tex1" * 8,
    "FO4PortTextures2.esm": b"TES4" + b"\0" * 38,
    "FO4PortTextures2 - Textures.ba2": b"BTDX" + b"tex2" * 8,
}
ORDER = ["FO4Port.esm", "FO4PortTextures2.esm"]


def sha(b):
    return hashlib.sha256(b).hexdigest()


class BatchInstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.stage, self.game = root / "interiors_b10", root / "game"
        (self.stage / "port").mkdir(parents=True)
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        self.pt = root / "Plugins.txt"
        for name, body in FILES.items():
            (self.stage / "port" / name).write_bytes(body)
        self.result = {"batch": 10, "pass": True, "error": None,
                       "pins": {"plugin": sha(FILES["FO4Port.esm"]), "core_plugin": sha(b"TES4core")},
                       "install": {"files": list(FILES), "plugins_txt": ORDER},
                       "steps": {"pack": {"sha256": {n: sha(b) for n, b in FILES.items() if n != "FO4Port.esm"}}}}
        self.write_result()

    def write_result(self):
        (self.stage / "result.json").write_text(json.dumps(self.result))

    def run_action(self, action, **kw):
        args = SimpleNamespace(action=action, staging="", batch=str(self.stage), starfield=str(self.game),
                               min_free_gb=0.0, dry_run=False, other_core=False, **kw)
        with patch.object(deploy, "plugins_txt_path", return_value=str(self.pt)):
            (deploy.install if action == "install" else deploy.uninstall)(args)

    def assert_untouched(self, plugins, data=()):
        self.assertEqual(sorted(p.name for p in self.data.iterdir()), sorted(data))
        self.assertEqual(self.pt.read_bytes(), plugins)

    def test_installs_the_set_with_companions_after_the_port_and_uninstalls_it(self):
        original = b"*Other.esm\r\nFO4Port.esm\r\n*Later.esm\r\n"
        self.pt.write_bytes(original)
        self.run_action("install")
        for name, body in FILES.items():
            self.assertEqual((self.data / name).read_bytes(), body)
        self.assertEqual(self.pt.read_text().splitlines(),
                         ["*Other.esm", "*FO4Port.esm", "*FO4PortTextures2.esm", "*Later.esm"])
        state = json.loads((self.data / deploy.MANIFEST).read_text())
        self.assertTrue(state["complete"])
        self.assertEqual(state["files"], list(FILES))
        self.assertEqual(state["plugins_added"], ["*FO4Port.esm", "*FO4PortTextures2.esm"])
        self.assertEqual({n: a["sha256"] for n, a in state["artifacts"].items()}, {n: sha(b) for n, b in FILES.items()})
        self.run_action("uninstall")
        self.assert_untouched(original)

    def test_appends_the_port_and_companions_when_neither_is_listed(self):
        self.pt.write_bytes(b"*Other.esm\n")
        self.run_action("install")
        self.assertEqual(self.pt.read_text().splitlines(), ["*Other.esm", "*FO4Port.esm", "*FO4PortTextures2.esm"])

    def test_a_file_that_is_not_the_pinned_build_installs_nothing(self):
        self.pt.write_bytes(b"*Other.esm\n")
        (self.stage / "port" / "FO4PortTextures2 - Textures.ba2").write_bytes(b"BTDX" + b"else" * 8)
        with self.assertRaisesRegex(SystemExit, "not the file the build pinned"):
            self.run_action("install")
        self.assert_untouched(b"*Other.esm\n")
        self.assertFalse((self.data / deploy.MANIFEST).exists())

    def test_refusals_before_anything_is_written(self):
        cases = {
            "did not pass": lambda r: r.update({"pass": False, "error": "compare failed"}),
            "no sha256 pinned": lambda r: r["steps"]["pack"]["sha256"].pop("FO4Port - Textures.ba2"),
            "does not match the files' companions": lambda r: r["install"].update({"plugins_txt": ["FO4Port.esm"]}),
            "not a port's set": lambda r: r["install"]["files"].append("Other.esm"),
        }
        for reason, change in cases.items():
            with self.subTest(reason=reason):
                self.setUp()
                self.pt.write_bytes(b"*Other.esm\n")
                change(self.result)
                self.write_result()
                with self.assertRaisesRegex(SystemExit, reason):
                    self.run_action("install")
                self.assert_untouched(b"*Other.esm\n")

    def test_a_companion_already_in_plugins_txt_is_refused(self):
        listed = b"*Other.esm\n*FO4PortTextures2.esm\n"
        self.pt.write_bytes(listed)
        with self.assertRaisesRegex(SystemExit, "already lists FO4PortTextures2.esm"):
            self.run_action("install")
        self.assert_untouched(listed)

    def test_free_space_floor(self):
        self.pt.write_bytes(b"*Other.esm\n")
        need = sum(len(b) for b in FILES.values())
        usage = SimpleNamespace(total=0, used=0, free=need + 1024 ** 3)
        with patch.object(deploy.shutil, "disk_usage", return_value=usage):
            with self.assertRaisesRegex(SystemExit, "under --min-free-gb 2"):
                self.run_with_floor(2.0)
            self.run_with_floor(0.5)
        self.assertTrue((self.data / deploy.MANIFEST).exists())

    def run_with_floor(self, gb):
        args = SimpleNamespace(action="install", staging="", batch=str(self.stage), starfield=str(self.game),
                               min_free_gb=gb, dry_run=False, other_core=False)
        with patch.object(deploy, "plugins_txt_path", return_value=str(self.pt)):
            deploy.install(args)

    def test_a_core_other_than_the_one_the_doors_were_wired_to_is_refused(self):
        self.pt.write_bytes(b"*Other.esm\n")
        (self.data / "FO4TerrainCore.esm").write_bytes(b"TES4other")
        with self.assertRaisesRegex(SystemExit, "doors were wired against"):
            self.run_action("install")
        self.assert_untouched(b"*Other.esm\n", ["FO4TerrainCore.esm"])
        args = SimpleNamespace(action="install", staging="", batch=str(self.stage), starfield=str(self.game),
                               min_free_gb=0.0, dry_run=False, other_core=True)
        with patch.object(deploy, "plugins_txt_path", return_value=str(self.pt)):
            deploy.install(args)
        self.assertTrue((self.data / deploy.MANIFEST).exists())

    def test_a_batch_without_a_core_pin_is_refused_while_a_core_is_installed(self):
        self.pt.write_bytes(b"*Other.esm\n")
        (self.data / "FO4TerrainCore.esm").write_bytes(b"TES4core")
        del self.result["pins"]["core_plugin"]
        self.write_result()
        with self.assertRaisesRegex(SystemExit, "pins no core"):
            self.run_action("install")
        self.assert_untouched(b"*Other.esm\n", ["FO4TerrainCore.esm"])

    def test_the_same_core_installs(self):
        self.pt.write_bytes(b"*Other.esm\n")
        (self.data / "FO4TerrainCore.esm").write_bytes(b"TES4core")
        self.run_action("install")
        self.assertTrue((self.data / deploy.MANIFEST).exists())

    def test_uninstall_refuses_a_manifest_naming_a_foreign_plugin_line(self):
        self.pt.write_bytes(b"*Other.esm\n*FO4Port.esm\n")
        deploy.write_manifest(str(self.data / deploy.MANIFEST), {"files": [], "plugins_txt": str(self.pt),
                              "plugins_added": ["*FO4Port.esm", "*Other.esm"], "complete": True})
        with self.assertRaisesRegex(SystemExit, "unexpected plugin cleanup entry"):
            self.run_action("uninstall")
        self.assertEqual(self.pt.read_bytes(), b"*Other.esm\n*FO4Port.esm\n")


class InstalledPortTests(unittest.TestCase):
    """deploy_starfield.py verify (cycle.ps1 with FO4SF_PORT=installed, 2026-10-28): a launch that tests the installed
    port checks it against its own record instead of redeploying a staging over it. Reads only."""
    setUp, write_result, run_action = BatchInstallTests.setUp, BatchInstallTests.write_result, BatchInstallTests.run_action

    def check(self):
        return deploy.installed_port(str(self.data), str(self.pt))

    def verify(self, pin=""):
        args = SimpleNamespace(starfield=str(self.game), plugin_sha256=pin)
        with patch.object(deploy, "plugins_txt_path", return_value=str(self.pt)), patch("builtins.print") as out:
            try:
                deploy.verify(args)
            except SystemExit as e:
                return e.code, out.call_args[0][0]
        return 0, out.call_args[0][0]

    def installed(self):
        self.pt.write_bytes(b"*Other.esm\n")
        self.run_action("install")
        return self.pt.read_bytes(), sorted(p.name for p in self.data.iterdir())

    def test_the_recorded_install_passes_and_nothing_is_touched(self):
        plugins, names = self.installed()
        self.assertEqual(self.check(), (None, sha(FILES["FO4Port.esm"])))
        code, line = self.verify(pin=sha(FILES["FO4Port.esm"]).upper())
        self.assertEqual(code, 0)
        self.assertIn(sha(FILES["FO4Port.esm"])[:8], line)
        self.assertEqual((self.pt.read_bytes(), sorted(p.name for p in self.data.iterdir())), (plugins, names))

    def test_another_pinned_plugin_is_refused(self):
        self.installed()
        code, line = self.verify(pin="ab" * 32)
        self.assertEqual(code, 1)
        self.assertIn("the run pinned abababab", line)
        (self.data / "FO4Port.esm").write_bytes(b"TES4" + b"swap" * 8)
        self.assertEqual(self.verify()[0], 1)                                   # changed, with or without a pin

    def test_a_file_swapped_in_by_hand_is_not_the_recorded_install(self):
        self.installed()
        (self.data / "FO4Port - Main.ba2").write_bytes(b"BTDX" + b"swap" * 8)
        self.assertIn("FO4Port - Main.ba2 changed since the install", self.check()[0])
        (self.data / "FO4Port - Main.ba2").unlink()
        self.assertIn("FO4Port - Main.ba2 is missing", self.check()[0])

    def test_every_owned_plugin_must_be_active(self):
        self.installed()
        lines = self.pt.read_text().splitlines()
        self.pt.write_text("\n".join(ln.lstrip("*") if ln == "*FO4PortTextures2.esm" else ln for ln in lines))
        self.assertEqual(self.check(), ("FO4PortTextures2.esm not active in Plugins.txt", None))
        self.pt.write_text("*Other.esm\n")
        self.assertIn("FO4Port.esm", self.check()[0])

    def test_no_or_an_unfinished_record_is_refused(self):
        self.assertIn("nothing installed", self.check()[0])
        self.installed()
        man = self.data / deploy.MANIFEST
        state = json.loads(man.read_text())
        man.write_text(json.dumps(dict(state, complete=False)))
        self.assertIn("interrupted", self.check()[0])
        man.write_text(json.dumps(dict(state, files=state["files"][1:])))     # FO4Port.esm no longer owned
        self.assertIn("not a port's recorded set", self.check()[0])
        man.write_text(json.dumps(dict(state, plugins_txt=str(self.pt) + ".other")))
        self.assertIn("not this user's", self.check()[0])
        man.write_text("{")
        self.assertIn("cannot be read", self.check()[0])


if __name__ == "__main__":
    unittest.main()
