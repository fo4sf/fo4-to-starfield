"""testqueue.py run with the controller lease (docs/ai/leader-core.md section 6, task T2): without a lease folder the
runner is unchanged; with one, nothing is launched or stepped unless its owner holds an unexpired lease there, and the
lease is renewed before every test. cycle.ps1 / watchdog.ps1 are checked as text here (PowerShell parses them on
Windows, tests/test_game_scripts.py). Synthetic data; no game, no Windows calls."""
import datetime
import json
import os
import subprocess
import re
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

    def test_the_whole_cycle_output_is_kept_in_cycle_log(self):
        # v6e doors_out, 2026-10-21: run.log kept only cycle.ps1's last line, so where the launch stopped was lost
        c.Controller(self.leader).claim("Claude", "window", 3600)
        r = self.runner(lease_dir=self.leader, lease_owner="Claude", max_attempts=1)
        r.session, r.cell, self.ctl.pid = False, None, None
        out = "main menu after 12 s\nsave loaded: not seen within 120 s, going on\nlease refused: not launching"
        r._ps = lambda script, args, timeout, steal=False: (9, out) if script == "cycle.ps1" else (0, "")
        with mock.patch.object(tq.Runner, "pinned_ok", return_value=True):
            r.run()
        with open(os.path.join(self.d, "cycle.log"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn(": exit 9\n" + out, text)

    def test_a_timed_out_script_keeps_what_it_printed(self):
        # Codex on #439: a cycle.ps1 past its budget kept only "timeout", none of its launch lines
        r = self.runner()
        err = subprocess.TimeoutExpired(["cycle.ps1"], 900, output=b"main menu after 12 s\n", stderr=None)
        with mock.patch.object(tq.subprocess, "run", side_effect=err):
            code, out = tq.Runner._ps(r, "cycle.ps1", [], 900)
        self.assertEqual((code, out), (124, "main menu after 12 s\ntimeout"))
        with mock.patch.object(tq.subprocess, "run", side_effect=subprocess.TimeoutExpired(["x"], 1)):
            self.assertEqual(tq.Runner._ps(r, "cycle.ps1", [], 1), (124, "timeout"))

    def _launch(self, codes, blocked=lambda launches: None):
        c.Controller(self.leader).claim("Claude", "window", 3600)
        r = self.runner(lease_dir=self.leader, lease_owner="Claude", max_attempts=1)
        r.session, r.cell, self.ctl.pid = False, None, None                   # no game: it has to be launched
        calls, checks = [], []

        def ps(script, args, timeout, steal=False):
            calls.append(script)
            return (codes.pop(0) if codes else 0, "x") if script == "cycle.ps1" else (0, "")

        def why(*a, **k):
            checks.append(1)
            return blocked(calls.count("cycle.ps1"))
        r._ps = ps
        with mock.patch.object(tq.Runner, "pinned_ok", return_value=True), \
                mock.patch.object(tq, "blocked_reason", side_effect=why):
            code = r.run()
        return code, calls

    def test_a_game_that_never_starts_stops_after_three_guarded_launches(self):
        code, calls = self._launch([10, 10, 10, 10])
        self.assertEqual(code, 3)
        self.assertEqual(calls, ["cycle.ps1"] * 3)                             # three launches, no relaunch per test
        with open(os.path.join(self.d, "run.log"), encoding="utf-8") as f:
            self.assertIn("the game did not stay up (launch 2 of 3): launching again", f.read())
        self.assertTrue(self.status().startswith("stopped: the game did not start (cycle.ps1 exit 10 on 3 launches"),
                        self.status())
        self.assertEqual(self.calls, [])

    def test_a_relaunch_after_a_dead_start_rechecks_every_launch_control(self):
        # Codex's review of #358: a STOP (or a lost lease, the owner back) between two launches is honoured
        code, calls = self._launch([10, 0], blocked=lambda launches: "STOP file present" if launches else None)
        self.assertEqual(calls, ["cycle.ps1"])                                 # no second Steam launch
        self.assertEqual(code, 3)
        self.assertIn("STOP", self.status())

    def test_cycle_ps1_launches_once_and_exits_10_when_the_game_does_not_stay_up(self):
        src = read(os.path.join(GAME, "cycle.ps1"))
        self.assertEqual(src.count("$launch = 'steam://rungameid/1716740'"), 1)
        self.assertEqual(src.count("Start-Process $launch"), 1)
        self.assertNotIn("for ($try", src)                                     # retries are the runner's, after its checks
        self.assertIn("Get-Process -Id $q.Id", src)                            # alive 20 s later, not just seen once
        self.assertLess(src.index("if (-not $q) {"), src.index("Wait-Screen 'main menu'"))
        self.assertIn("exit 10", src)

    def test_cycle_ps1_starts_starfield_exe_only_on_the_opt_in(self):
        src = read(os.path.join(GAME, "cycle.ps1"))
        start = src.index("$launch = 'steam://rungameid/1716740'")
        block = src[start:src.index("$q = $null", start)]
        self.assertIn("if ($env:FO4SF_LAUNCH -eq 'exe') {", block)             # opt-in only; steam:// otherwise
        self.assertIn("$launch = Join-Path $sf 'Starfield.exe'", block)
        self.assertLess(block.index("Test-Path -LiteralPath $launch"), block.index("Start-Process -FilePath $launch"))
        self.assertIn("exit 10", block)                                       # a missing exe is a dead start
        self.assertEqual(src.count("Start-Process -FilePath $launch -WorkingDirectory $sf"), 1)
        self.assertIn("after $launch (screen: $Shot)", src)

    def test_cycle_ps1_waits_long_enough_for_the_first_v6e_load(self):
        # 2026-10-21: the first v6e launch reached gameplay after both 120 s waits ran out, so coc.ps1 saw no HUD
        src = read(os.path.join(GAME, "cycle.ps1"))
        menu = int(re.search(r"Wait-Screen 'main menu' (\d+)", src).group(1))
        save = int(re.search(r"Wait-Screen 'save loaded' (\d+)", src).group(1))
        self.assertGreaterEqual(menu, 240)
        self.assertGreaterEqual(save, 300)
        start = 12 + 150 + 20 + 10                                             # close an old game, see it start, alive, settle
        cell = int(re.search(r"Wait-Screen 'cell loaded' (\d+)", src).group(1))
        self.assertGreater(tq.CYCLE_TIMEOUT_S, start + menu + save + cell + 120)   # the runner never cuts a slow launch short

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

    def _limited(self, **kw):
        r = self.runner(max_attempts=1, **kw)
        r.session, r.cell, self.ctl.pid = False, None, None                   # no game: it has to be launched
        calls = []
        r._ps = lambda script, *a, **k: calls.append(script) or (0, "")
        return r, calls

    def test_the_crash_budget_stops_before_the_next_launch(self):
        r, calls = self._limited(crash_budget=1)
        r.state["crashes"] = 1
        self.assertEqual(r.run(), 3)
        self.assertEqual((calls, self.calls), ([], []))
        self.assertTrue(self.status().startswith("stopped: limit: 1 crash(es) and 0 start death(s) this run, --crash-budget 1"),
                        self.status())

    def test_a_crash_under_the_budget_still_launches(self):
        r, calls = self._limited(crash_budget=2)
        r.state["crashes"] = 1
        with mock.patch.object(tq.Runner, "pinned_ok", return_value=True), \
                mock.patch.object(tq.Runner, "setup_session", side_effect=RuntimeError("launched")), \
                self.assertRaisesRegex(RuntimeError, "launched"):
            r.run()                                                           # past the limit: the launch ran
        self.assertIn("cycle.ps1", calls)

    def test_the_disk_floor_stops_before_a_launch(self):
        r, calls = self._limited(min_free_gb=43, dump_drive="X:\\")
        with mock.patch.object(tq.shutil, "disk_usage", return_value=mock.Mock(free=30e9)) as du:
            self.assertEqual(r.run(), 3)
        du.assert_called_with("X:\\")
        self.assertEqual((calls, self.calls), ([], []))
        self.assertTrue(self.status().startswith("stopped: limit: 30.0 GB free on X:\\, --min-free-gb 43"),
                        self.status())
        r, calls = self._limited(min_free_gb=43, dump_drive="X:\\")
        with mock.patch.object(tq.shutil, "disk_usage", side_effect=OSError("no drive")):
            self.assertEqual(r.run(), 3)                                      # unreadable counts as too full
        self.assertEqual(calls, [])
        self.assertIn("unreadable", self.status())

    def test_starts_that_die_count_against_the_crash_budget(self):
        # Codex's review of #377: an exit-10 start can crash too, so the budget counts it before the next launch
        c.Controller(self.leader).claim("Claude", "window", 3600)
        r = self.runner(lease_dir=self.leader, lease_owner="Claude", max_attempts=1, crash_budget=1)
        r.session, r.cell, self.ctl.pid = False, None, None
        calls = []
        r._ps = lambda script, *a, **k: calls.append(script) or ((10, "x") if script == "cycle.ps1" else (0, ""))
        with mock.patch.object(tq.Runner, "pinned_ok", return_value=True), \
                mock.patch.object(tq, "blocked_reason", return_value=None):
            self.assertEqual(r.run(), 3)
        self.assertEqual(calls.count("cycle.ps1"), 1)                         # no second Steam launch
        self.assertTrue(self.status().startswith("stopped: limit: 0 crash(es) and 1 start death(s) this run, "
                                                 "--crash-budget 1"), self.status())

    def test_bad_limits_are_refused(self):
        for bad in (["--crash-budget", "-1"], ["--min-free-gb", "nan"], ["--min-free-gb", "-1"],
                    ["--min-free-gb", "inf"]):
            with self.subTest(bad=bad), mock.patch("sys.stderr"), self.assertRaises(SystemExit):
                tq.main(["run", "--queue", self.d] + bad)
        for kw in (dict(min_free_gb=float("nan")), dict(min_free_gb=-1.0), dict(crash_budget=-1)):
            with self.subTest(kw=kw):                                         # a caller that skips the parser
                self.assertTrue(tq.launch_limit(tt.args(**kw), {}).startswith("limit: bad"))
        r, calls = self._limited(min_free_gb=float("nan"))
        with mock.patch.object(tq.shutil, "disk_usage", return_value=mock.Mock(free=0)):
            self.assertEqual(r.run(), 3)
        self.assertEqual(calls, [])

    def test_the_limits_are_off_by_default(self):
        self.assertIsNone(tq.launch_limit(tt.args(), {"crashes": 9}))

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
        # QA on #179: python that cannot be resolved leaves $LASTEXITCODE as it was, and a reused host had a 0 there; the
        # gate resolves python first, clears the stale code (the global one: a plain assignment would shadow what native
        # commands set), catches an invocation error and reads only lease.py's own fresh exit code
        gate = src[block:src.index("Get-Process Starfield")]
        self.assertIn("if (-not (Get-Command python -ErrorAction SilentlyContinue)) {", gate)
        self.assertIn("cannot be checked: not launching\"; exit 9 }", gate)
        self.assertIn("$global:LASTEXITCODE = $null", gate)
        self.assertIn("try { $leaseOut = python -I \"$repo\\scripts\\game\\lease.py\" status --require $leaseOwner; $leaseCode = $LASTEXITCODE }", gate)
        self.assertIn("catch { $leaseOut = \"lease.py could not be run: $_\"; $leaseCode = $null }", gate)
        self.assertLess(gate.index("Get-Command python"), gate.index("$global:LASTEXITCODE = $null"))
        self.assertLess(gate.index("$global:LASTEXITCODE = $null"), gate.index("lease.py\" status --require"))
        self.assertIsNone(re.search(r"(?<![:\w])\$LASTEXITCODE\s*=", src))   # never a script-scope shadow of it

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

    @unittest.skipUnless(os.name == "nt" and shutil.which("powershell"), "runs cycle.ps1 in a reused PowerShell host on Windows only")
    def test_cycle_ps1_in_a_reused_host_fails_closed_when_python_cannot_run(self):
        # QA on #179: a host that already ran a command has $LASTEXITCODE = 0; python missing from PATH raised
        # CommandNotFoundException and left that 0 in place, so the old guard passed and the game lookup was reached.
        # Here cycle.ps1 runs with & inside a wrapper script (one host, not -File) over an empty lease folder; the
        # wrapper's Get-Process is a canary that exits 77 instead of looking at the game, so a gate that fails open is
        # seen as exit 77 and never as a launch.
        import subprocess
        empty, host = tempfile.mkdtemp(), tempfile.mkdtemp()
        cycle = os.path.join(GAME, "cycle.ps1")

        def q(s):
            return "'" + s.replace("'", "''") + "'"

        def reused_host(prelude):
            wrapper = os.path.join(host, "reused_host.ps1")
            with open(wrapper, "w", encoding="utf-8-sig") as f:
                f.write("function Get-Process { 'canary: Get-Process reached, the gate failed open'; exit 77 }\n"
                        + prelude + "\n$global:LASTEXITCODE = 0\n"
                        + "& " + q(cycle) + " -Staging " + q(os.path.join(empty, "no-staging"))
                        + " -Starfield " + q(os.path.join(empty, "no-game")) + "\nexit $LASTEXITCODE\n")
            env = dict(os.environ, FO4SF_LEASE_DIR=empty, FO4SF_LEASE_OWNER="Claude")
            return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", wrapper],
                                  capture_output=True, text=True, timeout=120, env=env)
        # python not resolvable (a PATH without it): refused before anything is invoked
        r = reused_host("$env:PATH = Join-Path $env:SystemRoot 'System32'")
        self.assertEqual(r.returncode, 9, r.stdout + r.stderr)
        self.assertIn("python not found", r.stdout)
        self.assertNotIn("canary", r.stdout)
        # python resolvable but setting no exit code (a shim): the host's stale 0 must not count as lease.py's exit 0
        r = reused_host("function python { }")
        self.assertEqual(r.returncode, 9, r.stdout + r.stderr)
        self.assertIn("(lease.py exit ): not launching", r.stdout)
        self.assertNotIn("canary", r.stdout)
        self.assertFalse(os.path.exists(os.path.join(empty, "no-game")))

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
