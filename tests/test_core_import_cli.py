"""leader_import.py (docs/ai/leader-core.md section 3): queues, the deploy manifest and install records into a ledger
from the command line; idempotent, fail-closed per source, the report at the end. Synthetic folders; no game."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core import import_cli as cli  # noqa: E402
from fo4sf.core.state import Ledger, fold  # noqa: E402


def write_queue(d, name, tests, rows):
    q = os.path.join(d, name)
    os.makedirs(q)
    with open(os.path.join(q, "queue.json"), "w", encoding="utf-8") as f:
        json.dump({"created": "2026-10-15T10:00:00", "staging": "C:/staging", "plugin_sha256": "ab" * 32,
                   "build_id": "abababab", "commit": "d628b56",
                   "tests": [{"id": t, "kind": "travel", "cell": "C", "ref": "0x1"} for t in tests]}, f)
    with open(os.path.join(q, "results.jsonl"), "w", encoding="utf-8") as f:
        for t, verdict, cls in rows:
            f.write(json.dumps({"id": t, "kind": "travel", "cell": "C", "ref": "0x1", "attempt": 1, "verdict": verdict,
                                "class": cls, "detail": "", "dir": f"{t}_a1", "t": "t1"}) + "\n")
    return q


class ImportCliTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.d = d.name
        self.parent = os.path.join(self.d, "testqueue")
        os.makedirs(self.parent)
        self.leader = os.path.join(self.parent, "leader")                 # no queue.json: skipped by --queues
        os.makedirs(self.leader)
        self.q1 = write_queue(self.parent, "walk_1015", ["w1", "w2"], [("w1", "PASS", ""), ("w2", "FAIL", "NOLOAD")])
        self.q2 = write_queue(self.parent, "cave_1015", ["c1"], [("c1", "INCONCLUSIVE", "BREAKER")])
        with open(os.path.join(self.parent, "overnight.log"), "w", encoding="utf-8") as f:
            f.write("not a folder\n")

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue().strip().splitlines()

    def test_queues_under_a_parent_import_once_and_the_report_follows(self):
        code, lines = self.run_cli("--ledger", self.leader, "--queues", self.parent)
        self.assertEqual(code, 0, lines)
        self.assertIn(f"queue {self.q2}: 3 event(s) added", lines)       # pin + 1 test + 1 row (cave sorts first)
        self.assertIn(f"queue {self.q1}: 5 event(s) added", lines)       # pin + 2 tests + 2 rows
        self.assertIn(f"{self.leader}: skipped (no queue.json)", lines)
        self.assertIn(f"total: 8 event(s) added to {os.path.join(self.leader, 'ledger.jsonl')}", lines)
        bullets = [ln for ln in lines if ln.startswith("- ")]
        self.assertEqual(len(bullets), 8)
        self.assertIn("build_id=abababab", bullets[4])
        s = fold(Ledger(os.path.join(self.leader, "ledger.jsonl")).read())
        self.assertEqual({k: v["status"] for k, v in s.tasks.items()},
                         {"walk_1015/w1": "completed", "walk_1015/w2": "completed", "cave_1015/c1": "circuit_broken"})
        self.assertEqual(s.campaigns, {"walk_1015", "cave_1015"})
        code, lines = self.run_cli("--ledger", self.leader, "--queues", self.parent, "--no-report")
        self.assertEqual(code, 0)
        self.assertIn("total: 0 event(s) added", lines[-1])
        self.assertFalse(any(ln.startswith("- ") for ln in lines))

    def test_an_unreadable_source_fails_alone_and_exits_one(self):
        with open(os.path.join(self.q2, "queue.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        code, lines = self.run_cli("--ledger", self.leader, "--queue", self.q1, "--queue", self.q2)
        self.assertEqual(code, 1)
        self.assertIn(f"queue {self.q1}: 5 event(s) added", lines)
        self.assertTrue(any(ln.startswith(f"queue {self.q2}: FAILED: ") for ln in lines), lines)
        self.assertIn("total: 5 event(s) added", lines[-9])
        self.assertIn("1 source(s) failed", lines[-9])
        self.assertEqual(len([ln for ln in lines if ln.startswith("- ")]), 8)   # the report still prints
        code, lines = self.run_cli("--ledger", self.leader, "--queues", os.path.join(self.d, "nowhere"))
        self.assertEqual(code, 1)
        self.assertIn("not a folder", lines[0])

    def test_deploy_and_install_records_after_the_queues(self):
        dep = os.path.join(self.d, "FO4Port.deploy.json")
        with open(dep, "w", encoding="utf-8") as f:
            json.dump({"files": ["FO4Port.esm"], "complete": True, "artifacts": {"FO4Port.esm": {"size": 1, "sha256": "ef" * 32}}}, f)
        inst = os.path.join(self.d, "FO4SFExp.install.json")
        with open(inst, "w", encoding="utf-8") as f:
            json.dump({"plugins": ["FO4SFExp.esm"], "plugins_replaced": [], "complete": True, "pack": "core64d"}, f)
        code, lines = self.run_cli("--ledger", os.path.join(self.leader, "ledger.jsonl"), "--queue", self.q1,
                                   "--deploy", dep, "--install", inst, "--active-after-load", "yes")
        self.assertEqual(code, 0, lines)
        self.assertEqual(lines[:3], [f"queue {self.q1}: 5 event(s) added", f"deploy {dep}: 1 event(s) added", f"install {inst}: 1 event(s) added"])
        s = fold(Ledger(os.path.join(self.leader, "ledger.jsonl")).read())
        self.assertEqual(s.build, {"build_id": "efefefef", "plugin_sha256": "ef" * 32})   # the deploy is the current pin
        self.assertEqual(s.plugins, [{"name": "FO4SFExp.esm", "active_after_load": True}])
        self.assertIn("plugins: FO4SFExp.esm", [ln for ln in lines if ln.startswith("- Pins")][0])
        self.assertEqual(self.run_cli("--ledger", self.leader, "--queue", self.q1, "--deploy", dep, "--install", inst)[1][-9],
                         f"total: 0 event(s) added to {os.path.join(self.leader, 'ledger.jsonl')}")

    def test_nothing_to_import_is_a_usage_error(self):
        with self.assertRaises(SystemExit) as cm:
            with contextlib.redirect_stderr(io.StringIO()):
                cli.main(["--ledger", self.leader])
        self.assertEqual(cm.exception.code, 2)

    def test_the_wrapper_runs_under_python_isolated(self):
        r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "leader_import.py"), "--ledger", self.leader,
                            "--queue", self.q1, "--no-report"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("5 event(s) added", r.stdout)


if __name__ == "__main__":
    unittest.main()
