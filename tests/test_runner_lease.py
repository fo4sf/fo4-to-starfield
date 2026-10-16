"""testqueue.py run with the controller lease (docs/ai/leader-core.md section 6, task T2): without a lease folder the
runner is unchanged; with one, nothing is launched or stepped unless its owner holds an unexpired lease there, and the
lease is renewed before every test. cycle.ps1 / watchdog.ps1 are checked as text here (PowerShell parses them on
Windows, tests/test_game_scripts.py). Synthetic data; no game, no Windows calls."""
import datetime
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
sys.path.insert(0, os.path.join(ROOT, "src"))
import testqueue as tq  # noqa: E402
import test_testqueue as tt  # noqa: E402  (FakeControls, make_queue, args: the runner without Windows or a game)
from fo4sf.core import controller as c  # noqa: E402
from fo4sf.core.model import now_iso, parse_iso  # noqa: E402
from fo4sf.core.state import Ledger  # noqa: E402

GAME = os.path.join(ROOT, "scripts", "game")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


class RunnerLeaseTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        tt.make_queue(self.d, n=2)
        self.leader = os.path.join(self.d, "leader")
        self.ctl = tt.FakeControls()
        self.calls = []

    def runner(self, **kw):
        r = tq.Runner(self.d, tt.args(**kw), ctl=self.ctl, step=lambda t, o: self.calls.append(t["id"]) or 0)
        r.session, r.cell = True, "C"                     # game already set up in the test cell
        r._ps = lambda *a, **k: (0, "at the cell")        # never a real PowerShell here
        return r

    def status(self):
        return json.load(open(os.path.join(self.d, "state.json"), encoding="utf-8"))["status"]

    def test_without_a_lease_folder_nothing_is_checked(self):
        r = self.runner()                                 # args() has no lease_dir at all (older callers)
        self.assertIsNone(r.lease)
        r.run()
        self.assertTrue(self.calls)
        self.assertNotIn("lease", read(os.path.join(self.d, "run.log")))
        r = self.runner(lease_dir="", lease_owner="Claude")
        self.assertIsNone(r.lease)

    def test_no_lease_stops_before_any_step(self):
        r = self.runner(lease_dir=self.leader, lease_owner="Claude")
        self.assertEqual(r.run(), 3)
        self.assertEqual(self.calls, [])
        self.assertTrue(self.status().startswith("stopped: lease no lease"), self.status())
        log = read(os.path.join(self.d, "run.log"))
        self.assertIn("controller lease: " + os.path.abspath(self.leader), log)
        self.assertIn("stopped: lease no lease: claim one first", log)

    def test_dry_run_reports_the_missing_lease_and_launches_nothing(self):
        self.ctl.pid = None                               # no game: a launch would be needed
        r = self.runner(lease_dir=self.leader, dry_run=True)
        self.assertEqual(r.run(), 3)
        self.assertEqual(self.calls, [])
        self.assertIn("stopped: lease no lease", read(os.path.join(self.d, "run.log")))

    def test_someone_elses_lease_stops(self):
        c.Controller(self.leader).claim("Codex", "review", 3600)
        r = self.runner(lease_dir=self.leader, lease_owner="Claude")
        self.assertEqual(r.run(), 3)
        self.assertEqual(self.calls, [])
        self.assertIn("held by Codex", self.status())

    def test_expired_lease_is_ambiguous_and_stops(self):
        past = (parse_iso(now_iso()) - datetime.timedelta(hours=2)).isoformat()
        c.Controller(self.leader).claim("Claude", "a window long gone", 60, now=past)
        r = self.runner(lease_dir=self.leader, lease_owner="Claude")
        self.assertEqual(r.run(), 3)
        self.assertEqual(self.calls, [])
        self.assertIn("ambiguous", self.status())

    def test_own_lease_runs_and_is_renewed_before_every_test(self):
        ctl = c.Controller(self.leader)
        lease = ctl.claim("Claude", "chain", 3600)
        r = self.runner(lease_dir=self.leader, lease_owner="Claude", max_attempts=1)
        r.run()
        self.assertEqual(sorted(set(self.calls)), ["0000_fall", "0001_fall"])
        after = ctl.read()
        self.assertEqual(after.status(), "held")
        self.assertIsNotNone(after.renewed)
        self.assertGreaterEqual(parse_iso(after.expires), parse_iso(lease.expires))
        kinds = [e.ev for e in Ledger(os.path.join(self.leader, "ledger.jsonl")).read()]
        self.assertEqual(kinds[0], "controller_claimed")
        self.assertEqual(kinds.count("controller_renewed"), len(self.calls))
        self.assertEqual(self.status(), "finished")

    def test_lease_lost_during_the_run_stops_at_the_next_test(self):
        ctl = c.Controller(self.leader)
        ctl.claim("Claude", "chain", 3600)
        taken = []

        def step(t, o):
            self.calls.append(t["id"])
            if not taken:                                 # after the first test the owner takes the controller back
                ctl.release("Claude")
                taken.append(True)
            return 0
        r = tq.Runner(self.d, tt.args(lease_dir=self.leader, lease_owner="Claude", max_attempts=1), ctl=self.ctl, step=step)
        r.session, r.cell = True, "C"
        r._ps = lambda *a, **k: (0, "at the cell")
        self.assertEqual(r.run(), 3)
        self.assertEqual(self.calls, ["0000_fall"])
        self.assertIn("released by Claude", self.status())

    def test_a_launch_is_gated_before_the_idle_check(self):
        ctl = tt.FakeControls()
        ctl.pid, ctl.idle, ctl.last_sent_tick = None, 5, None    # would otherwise say "owner active"
        gate = tq.LeaseGate(self.leader, "Claude")
        why = tq.blocked_reason(ctl, {"hours": [[0, 24]]}, launching=True, min_idle=900, lease=gate)
        self.assertTrue(why.startswith("lease no lease"), why)
        c.Controller(self.leader).claim("Claude", "window", 3600)
        self.assertIn("owner active", tq.blocked_reason(ctl, {"hours": [[0, 24]]}, launching=True, min_idle=900, lease=gate))
        self.assertIsNone(tq.blocked_reason(ctl, {"hours": [[0, 24]]}, lease=None))


class ScriptLeaseBlockTests(unittest.TestCase):
    """The PowerShell side, as text: the guarded blocks exist, sit before anything that touches the game, and the
    behaviour without the switch is the old one (PowerShell's parser checks the syntax in test_game_scripts.py)."""

    def test_cycle_checks_the_lease_before_touching_the_game(self):
        src = read(os.path.join(GAME, "cycle.ps1"))
        block = src.index("if ($env:FO4SF_LEASE_DIR) {")
        self.assertLess(block, src.index("Get-Process Starfield"))            # before the running game is looked at
        self.assertLess(block, src.index("deploy_starfield.py\" uninstall"))   # before anything is redeployed
        self.assertIn("lease.py\" status --dir $env:FO4SF_LEASE_DIR --require $leaseOwner", src)
        self.assertIn("exit 9", src)
        self.assertIn("else { 'Claude' }", src)                                # the default owner

    def test_watchdog_lease_mode_is_off_by_default_and_never_takes_a_held_lease(self):
        src = read(os.path.join(GAME, "watchdog.ps1"))
        self.assertIn("lease_dir = ''; lease_owner = 'watchdog'; lease_hours = 8.0", src)
        self.assertIn("if (-not $c.lease_dir -and $env:FO4SF_LEASE_DIR)", src)
        self.assertIn("--grep '^Claude'", src)                                 # the old activity source, switch off
        self.assertIn("if ($cfg.lease_dir) {", src)
        self.assertIn("$ls.status -eq 'held'", src)                            # a held lease is never taken
        self.assertIn("if ($cfg.lease_dir) { $go = ClaimLeaseForChain $cfg $idleH }", src)
        self.assertIn("-not $running -and (QueueLeft) -gt 0", src)             # the chain-start rule unchanged
        self.assertIn("$env:FO4SF_LEASE_DIR = $cfg.lease_dir; $env:FO4SF_LEASE_OWNER = $cfg.lease_owner", src)
        self.assertLess(src.index("$go = ClaimLeaseForChain"), src.index("starting the test chain"))

    def test_lease_wrapper_runs_the_controller_cli(self):
        import subprocess
        d = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, "-I", os.path.join(GAME, "lease.py"), "status", "--dir", d, "--require", "Claude"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("not valid for Claude", r.stdout)
        r = subprocess.run([sys.executable, "-I", os.path.join(GAME, "lease.py"), "claim", "--dir", d, "--owner", "Claude",
                            "--purpose", "window", "--ttl", "60"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, "-I", os.path.join(GAME, "lease.py"), "status", "--dir", d, "--require", "Claude"],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
