"""Paired generations with the actual synthetic terrain ESM writer and port commands.

Terrain/asset survey setup is adapted to the tiny master; this is not a private
full-size terrain check or native round trip. Actual core records/VMADs and both
port commands run. Separate controls exercise the production command guards.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "scripts/terrain"), str(ROOT / "src")]
import test_port_marker_callers as callers
import test_terrain_reference_identity as tri
import test_terrain_doors_writer as tdw
import make_core64c as core
import paired_stage as paired
import port_marker_store as store
import vmad_patch as vp


class PairedStageTests(unittest.TestCase):
    setUpClass = classmethod(tri.TerrainReferenceIdentityTests.setUpClass.__func__)

    def setUp(self):
        self.fixture = callers.PairedCallerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        evidence = os.environ.get("FO4SF_PAIRED_EVIDENCE_DIR")
        if evidence:
            target = Path(evidence) / self._testMethodName
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(self.fixture.root, target)
            self.fixture.root = target
            self.fixture.port = target / "port"
            self.fixture.directory = target / "reservations"
        self.root = self.fixture.root
        self.port = self.fixture.port
        self.store = self.fixture.directory
        self.initial = self.fixture.initial
        self.work, self.base_core = self.root / "work", self.root / "terrain"
        self.work.mkdir()
        self.base_core.mkdir()
        cluster_path = self.root / "doors.json"
        # Pick the SECOND existing source alone: allocation must retain 0x805,
        # rather than legacy cmd_port's sequential 0x804.
        port = callers.mc.port_index(str(self.port))
        cluster, _ = callers.mc.doors(self.fixture.refs, [self.fixture.case.sources[1]], port)
        cluster_path.write_bytes(paired.encoded(cluster))
        spec = dict(work=str(self.work), core=str(self.base_core), port=str(self.port),
                    cluster=str(cluster_path), sf_esm=str(self.master), sf_data=str(self.master.parent))
        self.request = self.root / "request.json"
        self.request_hash = paired.pin(spec, self.request)
        self.events = []
        self.fail_at = None
        self.original_port, self.original_check = vp.cmd_port, vp.cmd_check

    def boundary(self, name, args):
        self.events.append(name)
        # A distinct Python process cannot enter the reservation store at ANY
        # of the four real publication/check boundaries.
        code = ("import sys;sys.path.insert(0,sys.argv[1]);import port_marker_store as s;"
                "\ntry:\n with s.session(sys.argv[2],sys.argv[3]): pass"
                "\nexcept s.BusyError: sys.exit(23)")
        proc = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT / "scripts/terrain"),
                               str(self.store), args.paired.plan.sha256], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 23, proc.stdout + proc.stderr)
        if self.fail_at == name:
            raise RuntimeError("injected " + name)

    def synthetic_stage(self, args):
        self.boundary("core-write", args)
        args.paired.before_core(args)
        output = Path(args.out)
        output.mkdir()
        cluster = json.loads(Path(args.cluster).read_bytes())
        source = cluster["doors"][0]["src"]
        ref = copy.deepcopy(self.objects["refs"][0])
        ref["src"] = source
        door = tdw.TerrainDoorsWriterTests.door(ref, 0, int(cluster["doors"][0]["destination"]["id"], 16),
                                              arrival=(1, 2, 3))
        wanted = self.fixture.case.doors[1]
        door["destination"].update(copy.deepcopy(wanted["destination"]))
        # Use the reservation, NOT the legacy cluster's sequential number.
        door["destination"]["id"] = int(cluster["doors"][0]["destination"]["id"], 16)
        objects = dict(world="SyntheticWorld", bases=copy.deepcopy(self.objects["bases"]),
                       refs=[], doors=[door])
        params = copy.deepcopy(self.params)
        # Existing production merge policy; synthetic metadata only, not a new
        # in-game measurement. Nonzero offset must survive both port commands.
        params["overlays"][0]["planet_target_cell"] = [-12, -27]
        (output / "objects.json").write_bytes(paired.encoded(objects))
        (output / "overlays_params.json").write_bytes(paired.encoded(params))
        proc = subprocess.run([self.dotnet, str(self.writer), str(self.master), str(output)],
                              capture_output=True, text=True)
        (output / "writer.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return 0

    def synthetic_core_check(self, args):
        self.boundary("core-check", args)
        args.paired.require_core(args.out)
        path = Path(args.out)
        objects = json.loads((path / "objects.json").read_bytes())
        identities = json.loads((path / "formids.json").read_bytes())
        records = core.overlay_records.walk_plugin(str(path / "Synthetic.esm"))["records"]
        problems = core.door_record_problems(records, 0x01000000, objects, identities)
        self.assertEqual(problems, [])
        paired.publish(path / "offline_check.json", {"pass": True, "checks": [["synthetic raw doors", True]]})
        return 0

    def port_command(self, args):
        self.boundary("port-write", args)
        return self.original_port(args)

    def port_check(self, args):
        self.boundary("port-check", args)
        return self.original_check(args)

    def run_pair(self, name="generation", **kwargs):
        with mock.patch.object(core, "cmd_stage", self.synthetic_stage), \
                mock.patch.object(core, "cmd_check", self.synthetic_core_check), \
                mock.patch.object(vp, "cmd_port", self.port_command), \
                mock.patch.object(vp, "cmd_check", self.port_check):
            return paired.run(self.request, self.request_hash, self.store,
                              kwargs.pop("state", self.initial.sha256), self.root / name, **kwargs)

    def test_actual_core_esm_and_actual_port_cli_share_gap_and_verify(self):
        before = paired.inventory(self.port)
        receipt = self.run_pair()
        self.assertEqual(self.events, ["core-write", "core-check", "port-write", "port-check"])
        output = self.root / "generation"
        report = json.loads((output / "port/doors.json").read_bytes())
        self.assertEqual(report["doors"][0]["marker"], "000805")
        self.assertTrue((output / "core/Synthetic.esm").exists())
        self.assertEqual(before, paired.inventory(self.port))
        complete_hash = paired.sha(paired.read(output / "complete.json"))
        self.assertEqual(paired.verify(output, complete_hash, self.store, receipt["state_sha256"]), receipt)
        plugin = output / "port/FO4Port.esm"
        plugin.write_bytes(plugin.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "port differs"):
            paired.verify(output, complete_hash, self.store, receipt["state_sha256"])

    def test_failures_preserve_partial_outputs_and_require_fresh_explicit_retry(self):
        for failure in ("core-write", "core-check", "port-write", "port-check"):
            with self.subTest(failure=failure):
                self.fail_at = failure
                failed = self.root / failure
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    self.run_pair(failure)
                self.assertFalse((failed / "complete.json").exists())
                before = paired.inventory(failed)
                state = paired.sha(paired.read(self.store / "state.json"))
                self.fail_at = None
                with self.assertRaisesRegex(store.RecoveryRequired, "explicit pinned retry"):
                    self.run_pair(failure + "-implicit", state=state)
                self.assertFalse((self.root / (failure + "-implicit")).exists())
                self.run_pair(failure + "-retry", state=state, retry_of=failed,
                              retry_sha256=paired.sha(paired.read(failed / "intent.json")))
                self.assertEqual(before, paired.inventory(failed))
                self.assertTrue((failed / "reserved.json").exists())

    def test_stale_external_state_or_request_refuses_before_generation(self):
        with store.session(self.store, self.initial.sha256) as writer:
            next_plan = writer.reserve(self.fixture.case.base, self.fixture.map_raw,
                                       ["000003:Synthetic.esm"], plugin="FO4Port.esm")
        self.assertNotEqual(next_plan.sha256, self.initial.sha256)
        with self.assertRaises(ValueError):
            self.run_pair("stale-state")
        self.assertFalse((self.root / "stale-state").exists())
        (self.work / "late.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pinned inputs"):
            self.run_pair("changed-input", state=next_plan.sha256)
        self.assertFalse((self.root / "changed-input").exists())

    def test_completion_not_reused_as_failed_retry(self):
        self.run_pair()
        old = self.root / "generation"
        with self.assertRaisesRegex(ValueError, "completed generation"):
            self.run_pair("retry", retry_of=old, retry_sha256=paired.sha(paired.read(old / "intent.json")))
        self.assertFalse((self.root / "retry").exists())

    def test_core_mutated_after_its_check_cannot_get_completion(self):
        real = self.port_check
        def alter(args):
            result = real(args)
            plugin = Path(args.core) / "Synthetic.esm"
            plugin.write_bytes(plugin.read_bytes() + b"later drift")
            return result
        with mock.patch.object(self, "port_check", alter):
            with self.assertRaisesRegex(ValueError, "artifacts changed"):
                self.run_pair("drift")
        self.assertFalse((self.root / "drift/complete.json").exists())

    def test_runtime_or_source_pin_tamper_refuses_before_output(self):
        request = json.loads(self.request.read_bytes())
        request["writers"]["runtime:python"]["sha256"] = "0" * 64
        path = self.root / "bad-request.json"
        path.write_bytes(paired.encoded(request))
        with self.assertRaisesRegex(ValueError, "writer sources changed"):
            paired.run(path, paired.sha(path.read_bytes()), self.store, self.initial.sha256, self.root / "bad")
        self.assertFalse((self.root / "bad").exists())

    def test_abrupt_exit_after_core_keeps_bytes_and_reservations_for_retry(self):
        payload = self.root / "child.json"
        payload.write_bytes(paired.encoded(dict(master=str(self.master), writer=str(self.writer),
                                                dotnet=self.dotnet, params=self.params, objects=self.objects)))
        locator = self.root / "locator.json"
        code = '''import json,os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import test_paired_stage as fixture
data=json.loads(Path(sys.argv[2]).read_bytes())
t=fixture.PairedStageTests()
t._testMethodName="abrupt-child"
for name,value in data.items(): setattr(t,name,Path(value) if name in ("master","writer") else value)
t.setUp()
spec=json.loads(t.request.read_bytes())["spec"]
cluster=Path(spec["cluster"])
doors=json.loads(cluster.read_bytes())
doors["doors"][0]["src"]="000003:Synthetic.esm"
cluster.write_bytes(fixture.paired.encoded(doors))
t.request=t.root/"request-new-source.json"
t.request_hash=fixture.paired.pin(spec,t.request)
original=t.boundary
def boundary(name,args):
 original(name,args)
 if name=="port-write":
  Path(sys.argv[3]).write_text(json.dumps(dict(root=str(t.root),request=str(t.request),request_hash=t.request_hash)))
  os._exit(44)
t.boundary=boundary
t.run_pair("killed")
'''
        evidence = os.environ.get("FO4SF_PAIRED_EVIDENCE_DIR")
        child_evidence = (Path(evidence).parent / (Path(evidence).name + ".child")
                          if evidence else self.root / "child-cases")
        proc = subprocess.run([sys.executable, "-I", "-c", code, str(ROOT / "tests"),
                               str(payload), str(locator)], capture_output=True, text=True,
                              env=dict(os.environ, FO4SF_PAIRED_EVIDENCE_DIR=str(child_evidence)))
        self.assertEqual(proc.returncode, 44, proc.stdout + proc.stderr)
        child = json.loads(locator.read_bytes())
        self.root = Path(child["root"])
        self.store, self.request = self.root / "reservations", Path(child["request"])
        self.request_hash = child["request_hash"]
        failed = self.root / "killed"
        self.assertTrue((failed / "core/Synthetic.esm").exists())
        self.assertFalse((failed / "failure.json").exists())
        self.assertFalse((failed / "complete.json").exists())
        old = paired.inventory(failed)
        state = paired.sha(paired.read(self.store / "state.json"))
        self.assertNotEqual(state, self.initial.sha256)
        reservations = json.loads(paired.read(self.store / "state.json"))["reservations"]
        self.assertEqual(reservations["000003:synthetic.esm"], 0x806)
        self.assertEqual(reservations["000002:synthetic.esm"], 0x805)
        with self.assertRaises(ValueError):
            self.run_pair("stale-kill-retry", retry_of=failed,
                          retry_sha256=paired.sha(paired.read(failed / "intent.json")))
        with store.session(self.store, state):
            pass  # The OS released the killed writer's lease; no control cleared.
        self.run_pair("kill-retry", state=state, retry_of=failed,
                      retry_sha256=paired.sha(paired.read(failed / "intent.json")))
        self.assertEqual(old, paired.inventory(failed))

    def test_production_guards_refuse_planned_commands_without_lease(self):
        cluster = json.loads(Path(json.loads(self.request.read_bytes())["spec"]["cluster"]).read_bytes())
        cluster["doors_port"]["marker_state_sha256"] = self.initial.sha256
        path = self.root / "planned.json"
        path.write_bytes(paired.encoded(cluster))
        with self.assertRaisesRegex(ValueError, "held lease"):
            core.cmd_stage(SimpleNamespace(cluster=str(path)))
        directory = self.root / "planned-core"
        directory.mkdir()
        (directory / "paired-input.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "live reservation"):
            vp.cmd_port(SimpleNamespace(core=str(directory)))
        with self.assertRaisesRegex(ValueError, "live reservation"):
            core.check_stage(SimpleNamespace(out=str(directory)))


if __name__ == "__main__":
    unittest.main()
