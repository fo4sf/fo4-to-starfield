"""Actual process exclusion/death and reservation-only recovery; synthetic data."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "scripts/terrain"), str(ROOT / "src")]
import test_port_marker_ids as fixture
import port_marker_ids as ids
import port_marker_store as store


CHILD = '''
import os,sys
from pathlib import Path
repo=Path(sys.argv[1]); sys.path[:0]=[str(repo/'scripts/terrain'),str(repo/'src')]
import port_marker_store as store
mode,folder,pin=sys.argv[2:5]
if mode=='lock':
    try:
        with store.session(folder,pin): print('acquired')
    except store.BusyError:
        print('busy'); sys.exit(9)
else:
    original=store._replace_state
    def die(*args,**kwargs):
        if mode=='after': original(*args,**kwargs)
        os._exit(77)
    store._replace_state=die
    data=Path(sys.argv[5])
    with store.session(folder,pin) as writer:
        writer.reserve((data/'base.esm').read_bytes(),(data/'map.json').read_bytes(),
                       ['000003:Synthetic.esm'],plugin='FO4Port.esm')
'''


class PortMarkerStoreTests(unittest.TestCase):
    def setUp(self):
        evidence = os.environ.get("FO4SF_MARKER_STORE_EVIDENCE")
        self.temp = None
        if evidence:
            self.root = Path(tempfile.mkdtemp(prefix="case-", dir=evidence))
            (self.root / "test-name.txt").write_text(self.id(), encoding="utf-8")
        else:
            self.temp = tempfile.TemporaryDirectory()
            self.root = Path(self.temp.name)
        self.f = fixture.PortMarkerIdentityTests()
        self.f.setUp()
        self.folder = self.root / "store"
        (self.root / "base.esm").write_bytes(self.f.base)
        (self.root / "map.json").write_bytes(fixture.encoded(self.f.mapping))
        self.initial = self.initialize()

    def tearDown(self):
        if self.temp:
            self.temp.cleanup()

    def initialize(self):
        return store.initialize(self.folder, self.f.base, fixture.encoded(self.f.mapping),
                                self.f.patched, fixture.encoded(self.f.patched_map), self.f.doors,
                                plugin="FO4Port.esm", core_plugin="Core.esm")

    def reserve(self, writer, sources=("000003:Synthetic.esm",)):
        return writer.reserve(self.f.base, fixture.encoded(self.f.mapping), sources, plugin="FO4Port.esm")

    def child(self, mode, pin=None):
        proc = subprocess.run([sys.executable, "-I", "-B", "-c", CHILD, str(ROOT), mode,
                               str(self.folder), pin or self.initial.sha256, str(self.root)],
                              capture_output=True, text=True, timeout=20)
        (self.root / f"child-{mode}-{len(list(self.root.glob('child-*.json')))}.json").write_text(
            json.dumps({"exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}), encoding="utf-8")
        return proc

    def test_store_publishes_before_return_and_preserves_prior_intent_and_tombstones(self):
        with store.session(self.folder, self.initial.sha256) as writer:
            plan = self.reserve(writer)
            self.assertEqual((self.folder / "state.json").read_bytes(), plan.state)
            self.assertEqual(self.reserve(writer, []).state, plan.state)
        self.assertEqual((self.folder / f"previous-{self.initial.sha256}.json").read_bytes(), self.initial.state)
        self.assertEqual((self.folder / f"prepared-{plan.sha256}.json").read_bytes(), plan.state)
        self.assertEqual(len(list(self.folder.glob("intent-*.json"))), 1)
        self.assertEqual(len(list(self.folder.glob("committed-*.json"))), 1)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            with store.session(self.folder, self.initial.sha256):
                self.fail("stale pin accepted")
        with store.session(self.folder, plan.sha256) as writer:
            following = self.reserve(writer, ["000004:Synthetic.esm"])
        self.assertEqual(following.assignments["000004:synthetic.esm"], 0x807)

    def test_actual_second_process_is_excluded_until_session_ends(self):
        with store.session(self.folder, self.initial.sha256):
            child = self.child("lock")
            self.assertEqual(child.returncode, 9, child.stderr)
            self.assertIn("busy", child.stdout)
        child = self.child("lock")
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn("acquired", child.stdout)

    def test_restored_initial_state_cannot_reissue_a_committed_marker(self):
        with store.session(self.folder, self.initial.sha256) as writer:
            committed = self.reserve(writer)
        evidence = {p.name: p.read_bytes() for p in self.folder.glob("*-*.json")}
        (self.folder / "state.json").write_bytes(self.initial.state)
        with self.assertRaisesRegex(store.RecoveryRequired, "superseded"):
            with store.session(self.folder, self.initial.sha256) as writer:
                self.reserve(writer, ["000004:Synthetic.esm"])
        self.assertEqual((self.folder / "state.json").read_bytes(), self.initial.state)
        self.assertEqual(evidence, {p.name: p.read_bytes() for p in self.folder.glob("*-*.json")})
        self.assertEqual(committed.assignments["000003:synthetic.esm"], 0x806)

    def test_restored_intermediate_state_is_also_superseded(self):
        with store.session(self.folder, self.initial.sha256) as writer:
            middle = self.reserve(writer)
            latest = self.reserve(writer, ["000004:Synthetic.esm"])
        (self.folder / "state.json").write_bytes(middle.state)
        with self.assertRaisesRegex(store.RecoveryRequired, "superseded"):
            with store.session(self.folder, middle.sha256):
                self.fail("old intermediate generation accepted")
        self.assertEqual((self.folder / "state.json").read_bytes(), middle.state)
        (self.folder / "state.json").write_bytes(latest.state)
        with store.session(self.folder, latest.sha256) as writer:
            next_plan = self.reserve(writer, ["000005:Synthetic.esm"])
        self.assertEqual(next_plan.assignments["000005:synthetic.esm"], 0x808)

    def test_completion_without_its_intent_cannot_hide_a_rollback(self):
        with store.session(self.folder, self.initial.sha256) as writer:
            self.reserve(writer)
        intent = next(self.folder.glob("intent-*.json"))
        intent.rename(self.root / "preserved-missing-intent.json")
        (self.folder / "state.json").write_bytes(self.initial.state)
        with self.assertRaisesRegex(store.RecoveryRequired, "completion.*intent"):
            with store.session(self.folder, self.initial.sha256):
                self.fail("completion receipt was ignored")
        self.assertEqual((self.folder / "state.json").read_bytes(), self.initial.state)

    def test_recovery_cannot_restore_an_endpoint_superseded_by_later_reservations(self):
        with store.session(self.folder, self.initial.sha256) as writer:
            middle = self.reserve(writer)
            latest = self.reserve(writer, ["000004:Synthetic.esm"])
        token, _ = store._intent(self.initial.sha256, middle.sha256)
        (self.folder / f"committed-{token}.json").rename(self.root / "preserved-missing-completion.json")
        (self.folder / "state.json").write_bytes(self.initial.state)
        with self.assertRaisesRegex(store.RecoveryRequired, "superseded"):
            store.recover(self.folder, before_sha256=self.initial.sha256, after_sha256=middle.sha256)
        self.assertEqual((self.folder / "state.json").read_bytes(), self.initial.state)
        self.assertEqual((self.folder / f"prepared-{latest.sha256}.json").read_bytes(), latest.state)

    def interrupted(self, phase):
        planned = ids.reserve(self.initial.state, self.initial.sha256, self.f.base,
                              fixture.encoded(self.f.mapping), ["000003:Synthetic.esm"], plugin="FO4Port.esm")
        child = self.child(phase)
        self.assertEqual(child.returncode, 77, child.stderr)
        current = self.initial if phase == "before" else planned
        self.assertEqual((self.folder / "state.json").read_bytes(), current.state)
        with self.assertRaises(store.RecoveryRequired):
            with store.session(self.folder, current.sha256):
                self.fail("unresolved preparation accepted")
        with self.assertRaises(store.RecoveryRequired):
            store.recover(self.folder, before_sha256="0" * 64, after_sha256=planned.sha256)
        intent_before = {p.name: p.read_bytes() for p in self.folder.glob("intent-*.json")}
        self.assertEqual(store.recover(self.folder, before_sha256=self.initial.sha256,
                                       after_sha256=planned.sha256), planned.sha256)
        self.assertEqual(intent_before, {p.name: p.read_bytes() for p in self.folder.glob("intent-*.json")})
        with store.session(self.folder, planned.sha256) as writer:
            self.assertEqual(self.reserve(writer).assignments, planned.assignments)
            next_plan = self.reserve(writer, ["000004:Synthetic.esm"])
            self.assertEqual(next_plan.assignments["000004:synthetic.esm"], 0x807)

    def test_actual_process_death_before_replacement_recovers_planned_reservations(self):
        self.interrupted("before")

    def test_actual_process_death_after_replacement_recovers_without_reallocation(self):
        self.interrupted("after")

    def test_missing_state_and_partial_initialization_never_reinitialize(self):
        # Synthetic deletion models the original failure; the bootstrap's
        # prepared copy remains preserved as recovery evidence.
        (self.folder / "state.json").unlink()
        with self.assertRaises(FileNotFoundError):
            with store.session(self.folder, self.initial.sha256):
                self.fail("missing state accepted")
        with self.assertRaises(FileExistsError):
            self.initialize()
        other = self.root / "partial"
        real_write = store._write_once

        def interrupted_write(path, raw):
            if path.name == "state.json":
                path.write_bytes(raw[:5])
                raise OSError("injected initialization interruption")
            return real_write(path, raw)

        with mock.patch.object(store, "_write_once", side_effect=interrupted_write), self.assertRaises(OSError):
            store.initialize(other, self.f.base, fixture.encoded(self.f.mapping), self.f.patched,
                             fixture.encoded(self.f.patched_map), self.f.doors,
                             plugin="FO4Port.esm", core_plugin="Core.esm")
        with self.assertRaises(ValueError):
            with store.session(other, self.initial.sha256):
                self.fail("partial initialization accepted")
        self.assertEqual((other / "state.json").read_bytes(), self.initial.state[:5])

    def test_concurrent_edit_is_preserved_and_closed_writer_cannot_write(self):
        with self.assertRaises(store.RecoveryRequired):
            with store.session(self.folder, self.initial.sha256) as writer:
                (self.folder / "state.json").write_bytes(b"owner changed this")
                self.reserve(writer)
        self.assertEqual((self.folder / "state.json").read_bytes(), b"owner changed this")
        with self.assertRaisesRegex(OSError, "closed"):
            self.reserve(writer)

    def test_hardlinked_state_refuses_without_modifying_either_name(self):
        alias = self.root / "alias.json"
        os.link(self.folder / "state.json", alias)
        try:
            with self.assertRaisesRegex(OSError, "unproven"):
                with store.session(self.folder, self.initial.sha256):
                    self.fail("hardlinked state accepted")
            self.assertEqual(alias.read_bytes(), self.initial.state)
        finally:
            # Remove only the synthetic alias so the preserved fixture can be archived.
            alias.unlink()

    def test_changed_prepared_state_refuses_recovery_without_overwriting_current(self):
        planned = ids.reserve(self.initial.state, self.initial.sha256, self.f.base,
                              fixture.encoded(self.f.mapping), ["000003:Synthetic.esm"], plugin="FO4Port.esm")
        self.assertEqual(self.child("before").returncode, 77)
        prepared = self.folder / f"prepared-{planned.sha256}.json"
        prepared.write_bytes(prepared.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            store.recover(self.folder, before_sha256=self.initial.sha256, after_sha256=planned.sha256)
        self.assertEqual((self.folder / "state.json").read_bytes(), self.initial.state)
        self.assertFalse(list(self.folder.glob("committed-*.json")))

    def test_recovery_rejects_a_new_marker_below_the_previous_reserved_range(self):
        base, mapping = self.f.grown_base(0x810)
        with store.session(self.folder, self.initial.sha256) as writer:
            grown = writer.reserve(base, mapping, self.f.sources, plugin="FO4Port.esm")
        data = json.loads(grown.state)
        data["reservations"]["000003:synthetic.esm"] = 0x806
        raw = fixture.encoded(data)
        pin = hashlib.sha256(raw).hexdigest()
        ids.validate_state(raw, pin)  # Internally valid, but not an allocator transition.
        token, intent = store._intent(grown.sha256, pin)
        store._write_once(self.folder / f"previous-{grown.sha256}.json", grown.state)
        store._write_once(self.folder / f"prepared-{pin}.json", raw)
        store._write_once(self.folder / f"intent-{token}.json", intent)
        with self.assertRaisesRegex(store.RecoveryRequired, "append-only"):
            store.recover(self.folder, before_sha256=grown.sha256, after_sha256=pin)
        self.assertEqual((self.folder / "state.json").read_bytes(), grown.state)


if __name__ == "__main__":
    unittest.main()
