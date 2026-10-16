"""testqueue.py run with the controller lease (docs/ai/leader-core.md section 6, task T2): without a lease folder the
runner is unchanged; with one, nothing is launched or stepped unless its owner holds an unexpired lease there, and the
lease is renewed before every test. cycle.ps1 / watchdog.ps1 are checked as text here (PowerShell parses them on
Windows, tests/test_game_scripts.py). Synthetic data; no game, no Windows calls."""
import datetime
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

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


def quiet_log(r, msg):
    with open(r.log_p, "a", encoding="utf-8") as f:
        f.write(f"{tq.now()} {msg}\n")


class RunnerLeaseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = tmp.name
        tt.make_queue(self.d, n=2)
        self.leader = os.path.join(self.d, "leader")
        self.ctl = tt.FakeControls()
        self.calls = []

    def runner(self, **kw):
        r = tq.Runner(self.d, tt.args(**kw), ctl=self.ctl, step=lambda t, o: self.calls.append(t["id"]) or 0)
        r.log = lambda msg: quiet_log(r, msg)             # run.log only: the suite's output stays the result line
        r.session, r.cell = True, "C"                     # game already set up in the test cell
        r._ps = lambda *a, **k: (0, "at the cell")        # never a real PowerShell here
        return r

    def status(self):
        with open(os.path.join(self.d, "state.json"), encoding="utf-8") as f:
            return json.load(f)["status"]

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

    def test_a_transient_renewal_failure_does_not_stop_a_run_whose_lease_is_still_valid(self):
        ctl = c.Controller(self.leader)
        ctl.claim("Claude", "chain", 3600)
        original = c.Controller.renew
        calls = []

        def flaky(self_, owner, ttl_s=None, now=None):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError("[WinError 5] controller.json is open in another process")
            return original(self_, owner, ttl_s, now)
        with mock.patch.object(c.Controller, "renew", flaky):
            code = self.runner(lease_dir=self.leader, lease_owner="Claude", max_attempts=1).run()
        self.assertEqual(code, 0)
        self.assertEqual(len(self.calls), 2)
        log = read(os.path.join(self.d, "run.log"))
        self.assertEqual(log.count("lease renewal failed ([WinError 5]"), 1)
        self.assertIn("still valid, renewing again", log)
        self.assertEqual(ctl.read().status(), "held")

    def test_the_runner_hands_its_lease_to_cycle_ps1(self):
        r = self.runner(lease_dir=self.leader, lease_owner="Bob")                 # flags, nothing in the environment
        with mock.patch.dict(os.environ, {"FO4SF_LEASE_DIR": "C:\\elsewhere", "FO4SF_LEASE_OWNER": "Claude"}):
            env = r.ps_env(steal=True)
        self.assertEqual((env["FO4SF_LEASE_DIR"], env["FO4SF_LEASE_OWNER"]), (r.lease.dir, "Bob"))   # the effective ones
        self.assertEqual((env["FO4SF_NO_FOCUS_STEAL"], env["LEGACY"]), ("0", "1"))
        plain = self.runner()                                                      # no lease: nothing added, nothing removed
        with mock.patch.dict(os.environ, {"FO4SF_LEASE_DIR": "C:\\elsewhere"}, clear=False):
            env = plain.ps_env()
        self.assertEqual(env["FO4SF_LEASE_DIR"], "C:\\elsewhere")
        self.assertEqual(env["FO4SF_NO_FOCUS_STEAL"], "1")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertNotIn("FO4SF_LEASE_DIR", plain.ps_env())

    def test_cycle_ps1_refusing_the_lease_stops_the_run_instead_of_retrying_every_test(self):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        r = self.runner(lease_dir=self.leader, lease_owner="Claude", max_attempts=1)
        r.session, r.cell, self.ctl.pid = False, None, None                   # no game: it has to be launched
        calls = []

        def ps(script, args, timeout, steal=False):
            calls.append(script)
            return (9, "no valid controller lease for Claude in X (lease.py exit 1): not launching") if script == "cycle.ps1" else (0, "")
        r._ps = ps
        with mock.patch.object(tq.Runner, "pinned_ok", return_value=True):    # the staging pin is not the point here
            self.assertEqual(r.run(), 3)
        self.assertEqual(calls, ["cycle.ps1"])
        self.assertTrue(self.status().startswith("stopped: lease refused by cycle.ps1 (exit 9)"), self.status())
        self.assertEqual(self.calls, [])                                       # no step, no INCONCLUSIVE rows
        self.assertFalse(os.path.exists(os.path.join(self.d, "results.jsonl")))

    def test_main_reads_the_switches_from_the_environment(self):
        seen = {}

        class FakeRunner:
            def __init__(self, qdir, a):
                seen["qdir"], seen["a"] = qdir, a

            def run(self):
                return 0
        env = {"FO4SF_LEASE_DIR": self.leader, "FO4SF_LEASE_OWNER": "watchdog", "FO4SF_PREFLIGHT": "1"}
        with mock.patch.dict(os.environ, env), mock.patch.object(tq, "Runner", FakeRunner):
            self.assertEqual(tq.main(["run", "--queue", self.d]), 0)
        a = seen["a"]
        self.assertEqual((seen["qdir"], a.lease_dir, a.lease_owner), (self.d, self.leader, "watchdog"))
        with mock.patch.dict(os.environ, {"FO4SF_LEASE_DIR": "", "FO4SF_LEASE_OWNER": "", "FO4SF_PREFLIGHT": ""}), \
                mock.patch.object(tq, "Runner", FakeRunner):
            tq.main(["run", "--queue", self.d])
        a = seen["a"]
        self.assertEqual((a.lease_dir, a.lease_owner), ("", "Claude"))                     # off by default
        with mock.patch.dict(os.environ, env), mock.patch.object(tq, "Runner", FakeRunner):
            tq.main(["run", "--queue", self.d, "--lease-dir", "", "--lease-owner", "Bob"])   # flags win
        a = seen["a"]
        self.assertEqual((a.lease_dir, a.lease_owner), ("", "Bob"))

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
        self.assertIn("lease.py\" status --require $leaseOwner", src)        # the folder from the environment (quoting)
        self.assertNotIn("--dir $env:FO4SF_LEASE_DIR", src)
        self.assertIn("if ($null -eq $leaseCode -or $leaseCode -ne 0) {", src)   # python missing: fail closed
        self.assertIn("exit 9", src)
        self.assertIn("else { 'Claude' }", src)                                # the default owner

    def test_watchdog_lease_mode_is_off_by_default_and_never_takes_a_held_lease(self):
        src = read(os.path.join(GAME, "watchdog.ps1"))
        self.assertIn("lease_dir = ''; lease_owner = 'watchdog'; lease_hours = 8.0", src)
        self.assertIn("--grep '^Claude'", src)                                 # the old activity source, switch off
        self.assertIn("if ($cfg.lease_dir) {", src)
        self.assertIn("$ls.status -eq 'held' -and $ls.lease.owner -ne $cfg.lease_owner", src)   # another's held lease is never taken, its own is claimed again
        self.assertIn("$ls.lease.owner -ne $cfg.lease_owner) {", src)         # its own chain's renewals are not Claude's activity
        self.assertIn("$startLeaseDir = $env:FO4SF_LEASE_DIR", src)             # the start value, not the one it sets for the chain
        self.assertIn("if (-not $c.lease_dir -and $startLeaseDir)", src)
        self.assertIn("$c.lease_dir = \"$($c.lease_dir)\".TrimEnd('\\')", src)   # one folder for every process
        self.assertIn("if (-not [IO.Path]::IsPathRooted($c.lease_dir)) { $c.lease_dir = Join-Path $tq $c.lease_dir }", src)
        self.assertIn("if ($cfg.lease_dir) { $go = ClaimLeaseForChain $cfg $idleH }", src)
        self.assertIn("[string]$Root = 'C:\\Modding\\testqueue')", src)         # the default root unchanged
        self.assertIn("$tq = $Root", src)
        self.assertIn("-not $running -and (QueueLeft) -gt 0", src)             # the chain-start rule unchanged
        self.assertIn("$env:FO4SF_LEASE_DIR = $cfg.lease_dir; $env:FO4SF_LEASE_OWNER = $cfg.lease_owner", src)
        self.assertLess(src.index("$go = ClaimLeaseForChain"), src.index("starting the test chain"))
        self.assertIn("if (-not $ls -or $ls.status -notin @('none', 'released')) {", src)   # --force only for a takeover
        self.assertIn("--ttl $ttl @force 2>&1", src)
        self.assertNotIn("--ttl $ttl --force", src)
        self.assertIn("if (-not $out) { Note \"lease status unreadable (no output", src)   # python missing: said so

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "runs watchdog.ps1 -Once on Windows only")
    def test_watchdog_once_in_lease_mode_never_takes_a_held_lease(self):
        # a temp root (log, state, chain_queue.txt with one queue), a temp config in lease mode with threshold 0 and
        # no Codex, the lease held by Claude: one check must log the held lease and start no chain (there is no
        # chain.ps1 in the temp root, so a wrong start would also fail loudly in the log)
        import subprocess
        root = tempfile.mkdtemp()
        leader = os.path.join(root, "leader")
        c.Controller(leader).claim("Claude", "window", 3600)
        with open(os.path.join(root, "chain_queue.txt"), "w", encoding="utf-8") as f:
            f.write(os.path.join(root, "q1") + "\n")
        cfg = os.path.join(root, "watchdog.json")
        with open(cfg, "w", encoding="utf-8") as f:
            json.dump({"lease_dir": leader, "threshold_hours": 0, "check_minutes": 1, "codex": False}, f)
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(GAME, "watchdog.ps1"),
                            "-Once", "-Config", cfg, "-Root", root], capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = read(os.path.join(root, "watchdog.log"))
        self.assertIn("lease held by Claude", log)
        self.assertIn("chain not started", log)
        self.assertNotIn("starting the test chain", log)
        self.assertFalse(os.path.exists(os.path.join(root, "watchdog_state.json")))   # no start recorded
        self.assertEqual(c.Controller(leader).read().owner, "Claude")                 # the lease untouched

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "runs cycle.ps1's refusing path on Windows only")
    def test_cycle_ps1_exits_9_without_a_lease_before_touching_anything(self):
        # the refusing path needs no game: an empty lease folder, exit 9 before Get-Process / the deploy
        import subprocess
        empty = tempfile.mkdtemp()
        env = dict(os.environ, FO4SF_LEASE_DIR=empty, FO4SF_LEASE_OWNER="Claude")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(GAME, "cycle.ps1"),
                            "-Staging", os.path.join(empty, "no-staging"), "-Starfield", os.path.join(empty, "no-game")],
                           capture_output=True, text=True, timeout=120, env=env)
        self.assertEqual(r.returncode, 9, r.stdout + r.stderr)
        self.assertIn("not valid for Claude", r.stdout)
        self.assertIn("not launching", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(empty, "no-game")))       # nothing deployed, nothing created

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
