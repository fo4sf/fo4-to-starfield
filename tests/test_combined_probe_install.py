"""scripts/combined_probes/probe_install.py: the probe plugin's own deployment record, Plugins.txt line, status and
uninstall, on a synthetic stage (a temp game folder, a temp LOCALAPPDATA, the archive builder replaced by a stub; no
game, no Archive2). The stage is what make_combined_probe.stage() writes: the plugin, Data/Scripts/*.pex, plan.json."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ba2_fixture import archive_from_tree  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "combined_probes"))
sys.path.insert(0, str(ROOT / "scripts" / "game"))
import probe_install  # noqa: E402
import exp_install  # noqa: E402


def write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def stage(d, variant="default", plugin_bytes=b"TES4-probe-plugin", skip=()):
    """A stage folder in the builder's layout with a consistent plan.json."""
    pexes = {rel: f"pex-{rel}".encode() for rel in ("Data/Scripts/FOCC_ProbeQuest.pex", "Data/Scripts/FOCC_Probe.pex",
                                                    "Data/Scripts/FOCC_P10Quest.pex")}
    write(os.path.join(d, probe_install.PLUGIN), plugin_bytes)
    for rel, data in pexes.items():
        write(os.path.join(d, *rel.split("/")), data)
    outputs = {probe_install.PLUGIN: sha(plugin_bytes)}
    outputs.update({rel: sha(data) for rel, data in pexes.items()})
    plan = {"kind": "combined-probe", "plugin": probe_install.PLUGIN, "variant": variant, "build_id": sha(plugin_bytes)[:8],
            "plugin_sha256": sha(plugin_bytes), "skip": list(skip), "outputs": outputs}
    with open(os.path.join(d, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f)
    return d


class ProbeInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.game = os.path.join(root, "game")
        self.data = os.path.join(self.game, "Data")
        os.makedirs(self.data)
        self.staged = stage(os.path.join(root, "focc_probe_20261021"))
        self.local = os.path.join(root, "local")
        os.makedirs(os.path.join(self.local, "Starfield"))
        self.plugins = os.path.join(self.local, "Starfield", "Plugins.txt")
        write(self.plugins, b"# header\r\n*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n*FO4SFBridge.esm\r\n")
        self.old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.local
        self.old_build = exp_install.build_ba2

        def stub_build(a, root_dir, out):
            self.assertTrue(os.path.isdir(os.path.join(root_dir, "Scripts")))
            write(out, archive_from_tree(Path(root_dir)))
            return out
        exp_install.build_ba2 = stub_build
        self.a = SimpleNamespace(dir=self.staged, starfield=self.game)

    def tearDown(self):
        exp_install.build_ba2 = self.old_build
        if self.old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old_local
        self.tmp.cleanup()

    def lines(self):
        with open(self.plugins, encoding="utf-8-sig") as f:
            return f.read().splitlines()

    def record(self):
        with open(os.path.join(self.data, probe_install.RECORD), encoding="utf-8") as f:
            return json.load(f)

    def quiet(self, fn, *args):
        with contextlib.redirect_stdout(io.StringIO()):
            return fn(*args)

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            try:
                probe_install.main(list(argv) + ["--starfield", self.game])
                code = 0
            except SystemExit as e:
                code = e.code
        return code, out.getvalue()

    def test_install_records_files_and_activates_the_plugin_last(self):
        code, out = self.run_main("install", "--dir", self.staged)
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.exists(os.path.join(self.data, probe_install.PLUGIN)))
        self.assertTrue(os.path.exists(os.path.join(self.data, probe_install.ARCHIVE)))
        rec = self.record()
        self.assertTrue(rec["complete"])
        self.assertEqual((rec["variant"], rec["build_id"]), ("default", sha(b"TES4-probe-plugin")[:8]))
        self.assertEqual(sorted(rec["files"]), sorted([probe_install.PLUGIN, probe_install.ARCHIVE]))
        self.assertEqual(self.lines()[-1], "*FO4SFCombinedProbe.esm")
        self.assertEqual(self.lines()[:4], ["# header", "*FO4Port.esm", "*FO4TerrainCore.esm", "*FO4SFBridge.esm"])
        self.assertIn("variant default", out)

    def test_status_before_and_after(self):
        code, out = self.run_main("status")
        self.assertEqual((code, json.loads(out)), (0, {"installed": False, "mission_active": False}))
        self.run_main("install", "--dir", self.staged)
        code, out = self.run_main("status")
        st = json.loads(out)
        self.assertEqual((st["installed"], st["active"], st["complete"], st["variant"]), (True, True, True, "default"))
        write(self.plugins, b"*FO4Port.esm\r\n")                   # a launch / deploy rewrote Plugins.txt
        self.assertFalse(json.loads(self.run_main("status")[1])["active"])

    def test_second_install_is_a_no_op_and_reactivates_after_a_rewrite(self):
        self.quiet(probe_install.install, self.a)
        self.quiet(probe_install.install, self.a)
        self.assertEqual(self.lines().count("*FO4SFCombinedProbe.esm"), 1)
        write(self.plugins, b"*FO4Port.esm\r\n")
        self.quiet(probe_install.install, self.a)
        self.assertEqual(self.lines(), ["*FO4Port.esm", "*FO4SFCombinedProbe.esm"])
        self.assertTrue(self.record()["complete"])

    def test_another_variant_is_refused_until_uninstalled(self):
        self.quiet(probe_install.install, self.a)
        other = stage(os.path.join(self.tmp.name, "focc_probe_p3cells"), variant="p3cells", plugin_bytes=b"TES4-p3cells")
        code, out = self.run_main("install", "--dir", other)
        self.assertIn("another probe variant", str(code))                 # sys.exit(message): exit status 1 on the PC
        with self.assertRaises(SystemExit) as cm:
            self.quiet(probe_install.install, SimpleNamespace(dir=other, starfield=self.game))
        self.assertIn("another probe variant", str(cm.exception))
        self.assertIn("rule 2", str(cm.exception))
        self.quiet(probe_install.uninstall, self.a)
        self.quiet(probe_install.install, SimpleNamespace(dir=other, starfield=self.game))
        self.assertEqual(self.record()["variant"], "p3cells")

    def test_mission_plugin_active_refuses_the_install(self):
        write(self.plugins, b"*FO4Port.esm\r\n*FO4TerrainCore.esm\r\n*FO4SFMission.esm\r\n")
        with self.assertRaises(SystemExit) as cm:
            self.quiet(probe_install.install, self.a)
        self.assertIn("FO4SFMission.esm is active", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.data, probe_install.PLUGIN)))
        self.assertFalse(os.path.exists(os.path.join(self.data, probe_install.RECORD)))
        self.assertTrue(json.loads(self.run_main("status")[1])["mission_active"])
        write(self.plugins, b"*FO4Port.esm\r\nFO4SFMission.esm\r\n")      # inactive line: allowed
        self.quiet(probe_install.install, self.a)
        self.assertEqual(self.lines(), ["*FO4Port.esm", "FO4SFMission.esm", "*FO4SFCombinedProbe.esm"])

    def test_stage_that_changed_after_its_build_is_refused(self):
        write(os.path.join(self.staged, "Data", "Scripts", "FOCC_Probe.pex"), b"edited")
        with self.assertRaises(SystemExit) as cm:
            self.quiet(probe_install.install, self.a)
        self.assertIn("rule 6", str(cm.exception))
        os.remove(os.path.join(self.staged, "plan.json"))
        with self.assertRaises(SystemExit) as cm:
            self.quiet(probe_install.install, self.a)
        self.assertIn("plan.json missing", str(cm.exception))

    def test_a_file_the_plan_does_not_pin_is_refused(self):
        # Codex review of #431: install packs the whole Data tree, so an extra file would ride along unreviewed.
        write(os.path.join(self.staged, "Data", "Scripts", "Extra.pex"), b"unreviewed")
        with self.assertRaises(SystemExit) as cm:
            self.quiet(probe_install.install, self.a)
        self.assertIn("Data/Scripts/Extra.pex not in plan.json outputs", str(cm.exception))

    def test_uninstall_removes_only_what_it_added(self):
        write(self.plugins, b"*FO4Port.esm\r\nFO4SFCombinedProbe.esm\r\n")   # an inactive line from before: put back
        self.quiet(probe_install.install, self.a)
        self.assertEqual(self.lines(), ["*FO4Port.esm", "*FO4SFCombinedProbe.esm"])
        code, out = self.run_main("uninstall")
        self.assertEqual(code, 0, out)
        self.assertIn("removed Data\\FO4SFCombinedProbe.esm", out)
        self.assertEqual(self.lines(), ["*FO4Port.esm", "FO4SFCombinedProbe.esm"])
        for name in (probe_install.PLUGIN, probe_install.ARCHIVE, probe_install.RECORD):
            self.assertFalse(os.path.exists(os.path.join(self.data, name)), name)
        self.assertEqual(self.run_main("uninstall"), (0, "probe not installed\n"))

    def test_a_changed_installed_file_is_preserved_and_the_record_kept(self):
        self.quiet(probe_install.install, self.a)
        write(os.path.join(self.data, probe_install.PLUGIN), b"someone edited the installed plugin")
        with self.assertRaises(SystemExit):
            self.quiet(probe_install.uninstall, self.a)
        self.assertTrue(os.path.exists(os.path.join(self.data, probe_install.PLUGIN)))
        self.assertFalse(os.path.exists(os.path.join(self.data, probe_install.ARCHIVE)))
        self.assertTrue(self.record()["cleanup_pending"])
        self.assertNotIn("*FO4SFCombinedProbe.esm", self.lines())

    def test_existing_game_files_are_never_overwritten(self):
        write(os.path.join(self.data, probe_install.ARCHIVE), b"not ours")
        with self.assertRaises(SystemExit) as cm:
            self.quiet(probe_install.install, self.a)
        self.assertIn("refusing to overwrite", str(cm.exception))
        self.assertFalse(os.path.exists(os.path.join(self.data, probe_install.RECORD)))

    def test_incomplete_core_deployment_refuses(self):
        write(os.path.join(self.data, exp_install.deployment.MANIFEST), json.dumps({"complete": False}).encode())
        with self.assertRaises(SystemExit) as cm:
            self.quiet(probe_install.install, self.a)
        self.assertIn("probe not installed", str(cm.exception))

    def test_cli_needs_dir_for_install(self):
        code, _ = self.run_main("install")
        self.assertEqual(code, "install needs --dir <stage>")

    def test_runbook_and_builder_name_this_installer(self):
        for rel in ("docs/spikes/combined-core-probes.md", "scripts/combined_probes/make_combined_probe.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("probe_install.py", text, rel)
            for cmd in ("probe_install.py install", "probe_install.py uninstall"):
                self.assertIn(cmd, text, (rel, cmd))


if __name__ == "__main__":
    unittest.main()
