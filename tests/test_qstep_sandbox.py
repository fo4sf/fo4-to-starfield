"""End-to-end run of qstep.ps1's npc_nav step against a simulated console (tests/qstep_sandbox), judged by testqueue.
Opt-in (each scenario starts ~60 PowerShell processes, about 25 s): set FO4SF_QSTEP_SANDBOX=1 on Windows.

Safety: the real qstep.ps1, parse_npc.py and parse_getpos.py are copied into a temporary folder next to the sandbox
fakes, so every helper the step calls (input.ps1, console_open.ps1, readpos.ps1, shot*.ps1, ocr.ps1) is a fake that
never sends input; nothing in scripts/game is run except the copied step itself."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "scripts", "game")
SANDBOX = os.path.join(ROOT, "tests", "qstep_sandbox")
sys.path.insert(0, GAME)
import testqueue as tq  # noqa: E402

ENABLED = os.name == "nt" and os.environ.get("FO4SF_QSTEP_SANDBOX") == "1"
N0 = {"label": "N0_ptr", "travel": "coc QASmoke", "npc": "0000CF96", "a": [-8, -4, 0], "b": [5, 10, 0],
      "drop": 0.5, "settle_ms": 0, "method": "ptr_player", "reads_s": [0, 2, 4, 7], "control": True}
WORLD = {"player": [0, 0, 0], "arrival": [0, 0, 0], "actors": {}, "log": [], "speed": 4.0, "sel": None}
N1 = {"travel": "coc FO4CW_RedRocketSpawn", "a": [-987.43, 1128.23, 105.03], "b": [-976.46, 1144.69, 105.03],
      "anchor": {"ref": "02000800", "local": [-989.03, 1147.2, 105.14]}, "spawn_local": [-989.03, 1147.2, 105.14]}
MARS = {"anchor_id": "02000800", "anchor_pos": [2010.97, -2352.8, 85.14], "arrival": [2010.97, -2352.8, 85.14]}


@unittest.skipUnless(ENABLED, "opt-in: FO4SF_QSTEP_SANDBOX=1 on Windows")
class QstepNpcSandboxTests(unittest.TestCase):
    def run_step(self, plan=None, world=None):
        d = tempfile.mkdtemp(prefix="qstep_npc_")
        step_dir = os.path.join(d, "game")
        shutil.copytree(SANDBOX, step_dir)
        for f in ("qstep.ps1", "parse_npc.py", "parse_getpos.py"):
            shutil.copy(os.path.join(GAME, f), step_dir)
        state = os.path.join(d, "state.json")
        with open(state, "w") as f:
            json.dump(dict(WORLD, **(world or {})), f)
        t = tq.npc_test(0, dict(N0, **(plan or {})))
        spec, out = os.path.join(d, "spec.json"), os.path.join(d, "out")
        with open(spec, "w") as f:
            json.dump(t, f)
        env = dict(os.environ, FAKE_STATE=state, FO4SF_PYTHON=sys.executable, FO4SF_NO_FOCUS_STEAL="1", LEGACY="1")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            os.path.join(step_dir, "qstep.ps1"), "-Spec", spec, "-Out", out],
                           capture_output=True, text=True, env=env, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(out, "obs.json"), encoding="utf-8-sig") as f:
            obs = json.load(f)
        with open(state) as f:
            left = [k for k, a in json.load(f)["actors"].items() if not (a.get("disabled") and a.get("deleted"))]
        return tq.judge(t, obs, out), obs, left

    def check(self, want, plan=None, world=None, removed=True):
        v, obs, left = self.run_step(plan, world)
        self.assertEqual(v[:2], want, v[2])
        if removed:
            self.assertEqual(left, [], obs.get("cleanup"))
        return obs

    def test_walk_is_a_pass_and_the_actor_is_removed(self):
        obs = self.check(("PASS", "PASS"))
        self.assertEqual(obs["cleanup"]["via"], "prid")       # by the GetSelf id
        self.assertEqual(obs["command"], "PathToRef player")

    def test_no_walk_is_nonav(self):
        self.check(("FAIL", "NONAV"), world={"speed": 0.0})

    def test_stale_log_and_lost_selection_still_find_the_actor(self):
        obs = self.check(("PASS", "PASS"), world={"clear_fails": True, "lose_selection": True, "self_fmt": "none"})
        self.assertTrue(all(s["via"] == "plr" for s in obs["samples"]))

    def test_unconfirmed_spawn_is_removed_by_its_id(self):
        obs = self.check(("INCONCLUSIVE", "SPAWN"), world={"isid_ok": False})
        self.assertEqual(obs["cleanup"]["via"], "id")
        self.assertNotIn("samples", obs)                      # nothing commanded on an unconfirmed handle

    def test_world_frame_from_the_anchor(self):
        obs = self.check(("PASS", "PASS"), plan=N1, world=MARS)
        self.assertEqual(obs["offset_from"], "anchor")

    def test_failed_spawn_types_nothing_on_the_selection(self):
        obs = self.check(("INCONCLUSIVE", "SPAWN"), world={"spawn_fails": True}, removed=False)
        self.assertFalse(obs["cleanup"]["removed"])


if __name__ == "__main__":
    unittest.main()
