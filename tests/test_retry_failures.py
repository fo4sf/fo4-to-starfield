"""--retry-failures: merge into the prior stage; actual main() regressions."""
from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
spec = importlib.util.spec_from_file_location("convert_batch", root / "scripts" / "convert_batch.py")
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)

A, B, C = "meshes/ok.nif", "meshes/fail1.nif", "meshes/fail2.nif"


def convert_ok(name, pose=None, out_suffix=""):
    return {"ok": True, "out_name": Path(name).stem + (out_suffix or ""), "shapes": 1, "fallback_materials": 0}


def run_main(staging, collision, names, convert, extra=(), plan=None):
    src = SimpleNamespace(mesh_names=lambda pattern: list(names), mesh=lambda name: None)
    converter = SimpleNamespace(stats={}, material_errors={}, convert_nif=Mock(side_effect=convert))
    argv = ["convert_batch.py", "--fo4-data", "unused", "--staging", str(staging),
            "--content-resources", "unused", "--texconv", "unused",
            "--collision-template", str(collision), *extra]
    patches = [patch.object(sys, "argv", argv),
               patch.object(batch.pipeline, "Fo4Archives", return_value=src),
               patch.object(batch.pipeline, "Converter", return_value=converter),
               patch.object(batch.convert_static, "collision_template_from_nif", return_value=b"template"),
               patch("builtins.print")]
    if plan is not None:
        patches.append(patch.object(batch.placed_pose, "plan", side_effect=plan))
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        batch.main()
    return converter.convert_nif


class RetryFailuresTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.staging = Path(self.tmp.name) / "staging"
        self.collision = Path(self.tmp.name) / "collision.nif"
        self.collision.write_bytes(b"synthetic")

    def tearDown(self):
        self.tmp.cleanup()

    def _initial_abc(self):
        def convert(name):
            if name == A:
                return convert_ok(name)
            return {"ok": False, "reason": "boom:" + name}
        run_main(self.staging, self.collision, [A, B, C], convert, extra=["--limit", "10"])
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in man["items"]], [A])
        self.assertEqual([f["nif"] for f in man["failures"]], [B, C])

    def test_retry_merges_successes_into_prior_manifest(self):
        self._initial_abc()
        prior_a = json.loads((self.staging / "manifest.json").read_text())["items"][0]
        run_main(self.staging, self.collision, [A, B, C], convert_ok,
                 extra=["--retry-failures", "--limit", "10"])
        man = json.loads((self.staging / "manifest.json").read_text())
        sources = [it["source"] for it in man["items"]]
        self.assertEqual(sources, [A, B, C])
        self.assertEqual(man["items"][0]["form_index"], prior_a["form_index"])
        self.assertEqual(man["failures"], [])
        summary = json.loads((self.staging / "failure-summary.json").read_text())
        self.assertEqual(summary["failed_nifs"], [])
        state = json.loads((self.staging / "build-state.json").read_text())
        self.assertTrue(state["complete"])

    def test_limited_retry_keeps_unattempted_failures(self):
        self._initial_abc()
        convert = Mock(side_effect=convert_ok)
        run_main(self.staging, self.collision, [A, B, C], convert,
                 extra=["--retry-failures", "--limit", "1"])
        called = [c.args[0] for c in convert.call_args_list]
        self.assertEqual(called, [B])
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in man["items"]], [A, B])
        self.assertEqual([f["nif"] for f in man["failures"]], [C])
        summary = json.loads((self.staging / "failure-summary.json").read_text())
        self.assertEqual(summary["failed_nifs"], [C])
        state = json.loads((self.staging / "build-state.json").read_text())
        self.assertFalse(state["complete"])
        convert2 = Mock(side_effect=convert_ok)
        run_main(self.staging, self.collision, [A, B, C], convert2,
                 extra=["--retry-failures", "--limit", "1"])
        self.assertEqual([c.args[0] for c in convert2.call_args_list], [C])
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in man["items"]], [A, B, C])
        self.assertEqual(json.loads((self.staging / "failure-summary.json").read_text())["failed_nifs"], [])

    def test_retry_without_prior_manifest_refuses(self):
        self._initial_abc()
        (self.staging / "manifest.json").unlink()
        summary_path = self.staging / "failure-summary.json"
        before_summary = summary_path.read_bytes()
        convert = Mock(side_effect=convert_ok)
        with self.assertRaises(SystemExit) as caught:
            run_main(self.staging, self.collision, [A, B, C], convert,
                     extra=["--retry-failures", "--limit", "10"])
        self.assertIn("manifest.json", str(caught.exception))
        convert.assert_not_called()
        self.assertEqual(summary_path.read_bytes(), before_summary)
        self.assertFalse((self.staging / "manifest.json").exists())

    def test_retry_summary_describes_the_merged_stage(self):
        self._initial_abc()
        run_main(self.staging, self.collision, [A, B, C], convert_ok,
                 extra=["--retry-failures", "--limit", "1"])
        summary = json.loads((self.staging / "failure-summary.json").read_text())
        self.assertEqual(summary["successes"], 2)
        self.assertEqual(summary["total_shapes"], 2)
        self.assertEqual(summary["avg_shapes"], 1.0)
        self.assertEqual(summary["failed_nifs"], [C])
        self.assertEqual(summary["examples"], {"boom": [C]})   # B was resolved by this retry

    def test_tagged_pose_failure_keeps_its_pose_identity(self):
        for tags in ("", "|static_body", "|load_door|no_rig"):
            with self.subTest(tags=tags):
                self.assertEqual(batch.retry_nif_identity(f"{B}|xrgd:abc123{tags}"),
                                 (batch.source_identity(B), "xrgd", "abc123"))
        self.assertEqual(batch.retry_nif_identity(B), (batch.source_identity(B), "", ""))

    def test_legacy_summary_without_failed_nifs_refuses(self):
        self._initial_abc()
        summary_path = self.staging / "failure-summary.json"
        legacy = {"total_failures": 2, "reasons": {"boom": 2}, "examples": {"boom": [B, C]}}
        summary_path.write_text(json.dumps(legacy), encoding="utf-8")
        before_summary = summary_path.read_bytes()
        before_manifest = (self.staging / "manifest.json").read_bytes()
        with self.assertRaises(SystemExit) as caught:
            run_main(self.staging, self.collision, [A, B, C], convert_ok,
                     extra=["--retry-failures", "--limit", "10"])
        self.assertIn("failed_nifs", str(caught.exception))
        self.assertEqual(summary_path.read_bytes(), before_summary)
        self.assertEqual((self.staging / "manifest.json").read_bytes(), before_manifest)

    def test_manifest_interrupt_keeps_successful_retry_b(self):
        def convert(name, pose=None, out_suffix=""):
            if name == A:
                return convert_ok(name, pose, out_suffix)
            return {"ok": False, "reason": "boom:" + name}
        run_main(self.staging, self.collision, [A, B], convert, extra=["--limit", "10"])
        prior = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in prior["items"]], [A])
        self.assertEqual([f["nif"] for f in prior["failures"]], [B])
        real_write = batch.write_json_atomic

        def wrap(path, value):
            if Path(path).name == "manifest.json" and any(it.get("source") == B for it in (value.get("items") or [])):
                raise OSError("injected manifest publication")
            return real_write(path, value)

        with patch.object(batch, "write_json_atomic", side_effect=wrap):
            with self.assertRaises(OSError):
                run_main(self.staging, self.collision, [A, B], convert_ok,
                         extra=["--retry-failures", "--limit", "10"])
        after = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in after["items"]], [A])
        self.assertEqual([f["nif"] for f in after["failures"]], [B])
        # Review leftover: summary already cleared before the failed publication.
        summary_path = self.staging / "failure-summary.json"
        wiped = json.loads(summary_path.read_text())
        wiped["failed_nifs"] = []
        wiped["total_failures"] = 0
        summary_path.write_text(json.dumps(wiped), encoding="utf-8")
        run_main(self.staging, self.collision, [A, B], convert_ok,
                 extra=["--retry-failures", "--limit", "10"])
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in man["items"]], [A, B])
        self.assertEqual(man["items"][0]["form_index"], prior["items"][0]["form_index"])
        self.assertEqual(man["failures"], [])
        self.assertEqual(json.loads((self.staging / "failure-summary.json").read_text())["failed_nifs"], [])
        self.assertTrue(json.loads((self.staging / "build-state.json").read_text())["complete"])

    def test_retry_keeps_base_and_prior_xrgd_variants(self):
        a, b = "meshes\\ok.nif", "meshes\\fail1.nif"
        cell_path = Path(self.tmp.name) / "cell.json"
        cell_path.write_text(json.dumps({"cell": "C", "refs": [
            {"formkey": "01:Fallout4.esm", "type": "Static", "model": "ok.nif"},
            {"formkey": "02:Fallout4.esm", "type": "Static", "model": "fail1.nif"}]}), encoding="utf-8")

        def plan(refs, by_source, mesh):
            variants = []
            for it in by_source.values():
                key = "aaaa111111" if "ok.nif" in it["source"].lower() else "bbbb222222"
                variants.append(SimpleNamespace(
                    source=it["source"], key=key, suffix="_xrgd_" + key,
                    refs=["01:Fallout4.esm"], overrides={1: object()}, shift=2.0))
            return variants, {"posed_refs": len(variants), "variants": len(variants),
                              "refs_with_ragdoll": len(variants), "unchanged": 0, "single_body": 0}

        def convert(name, pose=None, out_suffix=""):
            if name == b and pose is None:
                return {"ok": False, "reason": "boom:" + name}
            return convert_ok(name, pose, out_suffix)

        extra = ["--cell-json", str(cell_path), "--limit", "10"]
        run_main(self.staging, self.collision, [a, b], convert, extra=extra, plan=plan)
        prior = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in prior["items"]], [a, a])
        self.assertNotIn("pose", prior["items"][0])
        self.assertEqual(prior["items"][1]["pose"]["key"], "aaaa111111")
        self.assertEqual([f["nif"] for f in prior["failures"]], [b])
        prior_ids = [(it["form_index"], it["editor_id"], it.get("pose", {}).get("key")) for it in prior["items"]]
        run_main(self.staging, self.collision, [a, b], convert_ok,
                 extra=["--retry-failures", *extra], plan=plan)
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual(len(man["items"]), 4)
        self.assertEqual([it["source"] for it in man["items"]], [a, a, b, b])
        self.assertNotIn("pose", man["items"][0])
        self.assertEqual(man["items"][1]["pose"]["key"], "aaaa111111")
        self.assertNotIn("pose", man["items"][2])
        self.assertEqual(man["items"][3]["pose"]["key"], "bbbb222222")
        self.assertEqual([(it["form_index"], it["editor_id"], it.get("pose", {}).get("key"))
                          for it in man["items"][:2]], prior_ids)
        self.assertNotEqual(man["items"][2]["form_index"], man["items"][3]["form_index"])
        self.assertNotEqual(man["items"][2]["editor_id"], man["items"][3]["editor_id"])
        self.assertEqual(man["failures"], [])
        self.assertTrue(json.loads((self.staging / "build-state.json").read_text())["complete"])

    def _cell(self, models):
        cell_path = Path(self.tmp.name) / "cell.json"
        refs = [{"formkey": f"{i+1:02d}:Fallout4.esm", "type": "Static", "model": m}
                for i, m in enumerate(models)]
        cell_path.write_text(json.dumps({"cell": "C", "refs": refs}), encoding="utf-8")
        return cell_path

    def _plan_for(self, keys):
        def plan(refs, by_source, mesh):
            variants = []
            for it in by_source.values():
                src = it["source"].replace("\\", "/").lower()
                key = keys[src]
                variants.append(SimpleNamespace(
                    source=it["source"], key=key, suffix="_xrgd_" + key,
                    refs=["01:Fallout4.esm"], overrides={1: object()}, shift=2.0))
            return variants, {"posed_refs": len(variants), "variants": len(variants),
                              "refs_with_ragdoll": len(variants), "unchanged": 0, "single_body": 0}
        return plan

    def test_retry_keeps_new_pose_failure_when_base_succeeds(self):
        b = "meshes\\fail1.nif"
        extra = ["--cell-json", str(self._cell(["fail1.nif"])), "--limit", "10"]
        plan = self._plan_for({"meshes/fail1.nif": "bbbb222222"})

        def convert_initial(name, pose=None, out_suffix=""):
            return {"ok": False, "reason": "boom:" + name}

        run_main(self.staging, self.collision, [b], convert_initial, extra=extra, plan=plan)
        prior = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual(prior["items"], [])
        self.assertEqual([f["nif"] for f in prior["failures"]], [b])

        def convert_retry(name, pose=None, out_suffix=""):
            if pose is not None:
                return {"ok": False, "reason": "pose-boom:" + name}
            return convert_ok(name, pose, out_suffix)

        run_main(self.staging, self.collision, [b], convert_retry,
                 extra=["--retry-failures", *extra], plan=plan)
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in man["items"]], [b])
        self.assertNotIn("pose", man["items"][0])
        self.assertEqual([f["nif"] for f in man["failures"]], [b + "|xrgd:bbbb222222"])
        summary = json.loads((self.staging / "failure-summary.json").read_text())
        self.assertEqual(summary["failed_nifs"], [b + "|xrgd:bbbb222222"])
        self.assertFalse(json.loads((self.staging / "build-state.json").read_text())["complete"])

    def test_pose_only_retry_resolves_base_and_aliases(self):
        b, c = "meshes\\fail1.nif", "meshes\\fail2.nif"
        extra = ["--cell-json", str(self._cell(["fail1.nif", "fail2.nif"])), "--limit", "10"]
        plan = self._plan_for({"meshes/fail1.nif": "bbbb222222", "meshes/fail2.nif": "cccc333333"})

        def convert_initial(name, pose=None, out_suffix=""):
            if pose is not None:
                return {"ok": False, "reason": "pose-boom:" + name}
            return convert_ok(name, pose, out_suffix)

        run_main(self.staging, self.collision, [b, c], convert_initial, extra=extra, plan=plan)
        prior = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual([it["source"] for it in prior["items"]], [b, c])
        self.assertEqual([f["nif"] for f in prior["failures"]],
                         [b + "|xrgd:bbbb222222", c + "|xrgd:cccc333333"])
        prior_ids = [(it["form_index"], it["editor_id"]) for it in prior["items"]]
        summary_path = self.staging / "failure-summary.json"
        summary = json.loads(summary_path.read_text())
        summary["failed_nifs"] = [n.replace("\\", "/") for n in summary["failed_nifs"]]
        summary_path.write_text(json.dumps(summary), encoding="utf-8")

        convert = run_main(self.staging, self.collision, [b, c], convert_ok,
                           extra=["--retry-failures", *extra], plan=plan)
        posed = [call for call in convert.call_args_list if call.kwargs.get("pose") is not None]
        self.assertEqual({call.args[0] for call in posed}, {b, c})
        man = json.loads((self.staging / "manifest.json").read_text())
        self.assertEqual(len(man["items"]), 4)
        self.assertEqual([it["source"] for it in man["items"]], [b, c, b, c])
        self.assertNotIn("pose", man["items"][0])
        self.assertNotIn("pose", man["items"][1])
        self.assertEqual(man["items"][2]["pose"]["key"], "bbbb222222")
        self.assertEqual(man["items"][3]["pose"]["key"], "cccc333333")
        self.assertEqual([(it["form_index"], it["editor_id"]) for it in man["items"][:2]], prior_ids)
        self.assertEqual(man["failures"], [])
        self.assertEqual(json.loads((self.staging / "failure-summary.json").read_text())["failed_nifs"], [])
        self.assertTrue(json.loads((self.staging / "build-state.json").read_text())["complete"])


if __name__ == "__main__":
    unittest.main()
