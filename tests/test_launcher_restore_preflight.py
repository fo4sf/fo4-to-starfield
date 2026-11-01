"""Restore must reject changed stages and incompatible target pins before the first installer call."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from fo4sf.launcher import restore  # noqa: E402

CORE, PORT = "FO4TerrainCore.esm", "FO4Port.esm"
ADDONS = {"bridge": "FO4SFBridge.esm", "markers": "FO4SFMapMarkers.esm",
          "quest_probe": "FO4SFQuestProbe.esm", "combined_probe": "FO4SFCombinedProbe.esm",
          "planet_probe": "FO4SFPlanetProbe.esm"}


class RestoreStagePreflightTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.game = self.root / "game"
        self.data = self.game / "Data"
        self.data.mkdir(parents=True)
        self.pt = self.root / "local" / "Starfield" / "Plugins.txt"
        self.pt.parent.mkdir(parents=True)
        self.payloads = {}
        self.a = self.stage("experiment", "core-a", CORE)
        self.b = self.stage("experiment", "core-b", CORE)
        digest = self.keep(b"synthetic-port")
        self.port = {"files": [PORT], "artifacts": {PORT: {"sha256": digest}}, "complete": True}

    def keep(self, raw):
        digest = hashlib.sha256(raw).hexdigest()
        self.payloads[digest] = raw
        return digest

    def stage(self, comp, name, plugin):
        directory = self.root / "stages" / name
        (directory / "Data" / "Scripts").mkdir(parents=True, exist_ok=True)
        plugin_bytes, pex = (name + "-plugin").encode(), (name + "-pex").encode()
        (directory / plugin).write_bytes(plugin_bytes)
        (directory / "Data" / "Scripts" / "Test.pex").write_bytes(pex)
        rec = {"files": {plugin: self.keep(plugin_bytes)}, "complete": True}
        data = {"Data/Scripts/Test.pex": self.keep(pex)}
        if comp in restore.EXP_KIT:
            rec.update(exp_dir=str(directory), plugins=[plugin], pack=True,
                       source_inputs={"plugin/" + plugin: self.keep(plugin_bytes), **data})
        else:
            rec.update(dir=str(directory), plugin=plugin,
                       source_sha256={plugin: self.keep(plugin_bytes), **data})
        return rec

    def publish(self, records):
        # Only this test's synthetic Data folder; no installed files or configuration paths are used.
        for path in self.data.iterdir():
            path.unlink()
        (self.data / "Starfield.esm").write_bytes(b"synthetic-master")
        for comp, rec in records.items():
            for name, digest in restore.owned_expected(comp, rec).items():
                (self.data / name).write_bytes(self.payloads[digest])
            (self.data / restore.COMPONENTS[comp][0]).write_text(json.dumps(rec), encoding="utf-8")
        names = sorted(restore.owned_plugins({"records": records}))
        self.pt.write_bytes(b"# synthetic owner's header\r\n" + b"".join(("*" + n + "\r\n").encode() for n in names))
        return restore.take(str(self.game), str(self.pt))

    def target(self, comp):
        rec = self.a if comp == "experiment" else self.stage(
            comp, comp, ADDONS[comp])
        directory = Path(restore.source_dir(comp, rec))
        if comp == "markers":
            (directory / "core.json").write_text(json.dumps({"masters": {CORE: self.a["files"][CORE]}}), encoding="utf-8")
        elif comp == "quest_probe":
            (directory / "plan.json").write_text(json.dumps({"checked_against_sha256": {
                PORT: self.port["artifacts"][PORT]["sha256"]}}), encoding="utf-8")
        target = self.publish({"experiment": self.a, "port": self.port, comp: rec})
        self.publish({"experiment": self.b, "port": self.port})
        return target, directory

    def unchanged(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.game.rglob("*") if p.is_file()}, self.pt.read_bytes()

    def refused(self, target, component, filename):
        p = restore.plan(target, restore.take(str(self.game), str(self.pt)), str(ROOT))
        self.assertTrue(any(component in s and filename in s for s in p["conflicts"]), p)
        before, calls = self.unchanged(), []

        def no_installer(*args, **kwargs):
            calls.append(args)
            raise AssertionError("preflight must refuse before any installer")

        with self.assertRaises(restore.RestoreRefused):
            restore.apply(target, str(ROOT), running=lambda: False, run=no_installer, echo=lambda *_: None)
        self.assertEqual(calls, [])
        self.assertEqual(self.unchanged(), before)

    def test_changed_staged_plugin_refuses_every_kit(self):
        for comp in ("experiment", *ADDONS):
            with self.subTest(component=comp):
                target, directory = self.target(comp)
                rec = target["records"][comp]
                name = rec.get("plugin") or rec["plugins"][0]
                (directory / name).write_bytes(b"restaged-in-place")
                self.refused(target, comp, name)

    def test_changed_staged_pex_refuses_every_kit(self):
        for comp in ("experiment", *ADDONS):
            with self.subTest(component=comp):
                target, directory = self.target(comp)
                (directory / "Data" / "Scripts" / "Test.pex").write_bytes(b"changed-pex")
                self.refused(target, comp, "Test.pex")

    def test_added_and_removed_data_inputs_refuse(self):
        for comp in ("experiment", "markers"):
            for added in (False, True):
                with self.subTest(component=comp, added=added):
                    target, directory = self.target(comp)
                    path = directory / "Data" / "Scripts" / ("Extra.pex" if added else "Test.pex")
                    path.write_bytes(b"unrecorded") if added else path.unlink()
                    self.refused(target, comp, path.name)

    def test_marker_pin_cannot_target_another_core(self):
        target, directory = self.target("markers")
        (directory / "core.json").write_text(json.dumps({"masters": {CORE: self.b["files"][CORE]}}), encoding="utf-8")
        self.refused(target, "markers", CORE)

    def test_marker_pin_needs_its_target_master(self):
        target, directory = self.target("markers")
        (directory / "core.json").write_text(json.dumps({"masters": {"UnknownCore.esm": "a" * 64}}), encoding="utf-8")
        self.refused(target, "markers", "UnknownCore.esm")

    def test_missing_marker_pin_refuses(self):
        target, directory = self.target("markers")
        (directory / "core.json").unlink()
        self.refused(target, "markers", "core.json")

    def test_quest_pin_cannot_target_another_port(self):
        target, directory = self.target("quest_probe")
        (directory / "plan.json").write_text(json.dumps({"checked_against_sha256": {PORT: "b" * 64}}), encoding="utf-8")
        self.refused(target, "quest_probe", PORT)

    def test_missing_quest_pin_refuses(self):
        target, directory = self.target("quest_probe")
        (directory / "plan.json").write_text("{}", encoding="utf-8")
        self.refused(target, "quest_probe", "plan.json")

    def test_malformed_pin_files_refuse(self):
        for comp, name in (("markers", "core.json"), ("quest_probe", "plan.json")):
            with self.subTest(component=comp):
                target, directory = self.target(comp)
                (directory / name).write_text("null", encoding="utf-8")
                self.refused(target, comp, name)

    def test_apply_rechecks_after_a_successful_dry_run(self):
        target, directory = self.target("markers")
        self.assertEqual(restore.plan(target, restore.take(str(self.game), str(self.pt)), str(ROOT))["conflicts"], [])
        (directory / "Data" / "Scripts" / "Test.pex").write_bytes(b"changed-after-dry-run")
        self.refused(target, "markers", "Test.pex")

    def test_matching_inputs_and_pins_have_no_conflict(self):
        for comp in ("experiment", *ADDONS):
            with self.subTest(component=comp):
                target, _ = self.target(comp)
                self.assertEqual(restore.plan(target, restore.take(str(self.game), str(self.pt)), str(ROOT))["conflicts"], [])

    def test_plugin_only_stage_does_not_require_a_data_tree(self):
        target, directory = self.target("experiment")
        (directory / "Data" / "Scripts" / "Test.pex").unlink()
        (directory / "Data" / "Scripts").rmdir()
        (directory / "Data").rmdir()
        del target["records"]["experiment"]["source_inputs"]["Data/Scripts/Test.pex"]
        self.assertEqual(restore.plan(target, restore.take(str(self.game), str(self.pt)), str(ROOT))["conflicts"], [])

    def test_pin_names_and_inventory_separators_are_portable(self):
        target, directory = self.target("markers")
        rec = target["records"]["markers"]
        rec["source_sha256"] = {k.replace("/", "\\"): v for k, v in rec["source_sha256"].items()}
        (directory / "core.json").write_text(json.dumps({"masters": {CORE.swapcase(): self.a["files"][CORE]}}), encoding="utf-8")
        self.assertEqual(restore.plan(target, restore.take(str(self.game), str(self.pt)), str(ROOT))["conflicts"], [])

    def test_legacy_experiment_is_not_claimed_verified(self):
        target, _ = self.target("experiment")
        del target["records"]["experiment"]["source_inputs"]
        p = restore.plan(target, restore.take(str(self.game), str(self.pt)), str(ROOT))
        self.assertEqual(p["conflicts"], [])
        self.assertTrue(any("experiment" in s and "source_inputs" in s for s in p["notes"]), p)

    def test_kept_install_does_not_need_its_stage(self):
        target, directory = self.target("markers")
        current = copy.deepcopy(target)
        (directory / "FO4SFMapMarkers.esm").unlink()
        p = restore.plan(target, current, str(ROOT))
        self.assertEqual((p["steps"], p["conflicts"]), ([], []))


if __name__ == "__main__":
    unittest.main()
