"""Movable items in the queued runner (scripts/game/testqueue.py): the walk, then the ApplyHavokImpulse ladder; items on
furniture are ELEVATED, not NOTMOVED; movable_control plans (an item placed in a vanilla cell) are validated before
anything can be typed. Synthetic data; no game, no PowerShell (tests/test_qstep_sandbox.py runs the step itself)."""
import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts", "game"))
import runner_features  # noqa: E402
import testqueue as tq  # noqa: E402


def jdump(obj, p):
    with open(p, "w") as f:
        json.dump(obj, f)


def jload(p):
    with open(p) as f:
        return json.load(f)


def touch(d, name):
    open(os.path.join(d, name), "wb").close()
    return name


ITEM = {"label": "C_burntbook", "travel": "coc QASmoke", "base": "0200CE2A", "mass_kg": 25.0, "spot": [-3.0, 4.0, 0.0]}


def push_obs(d, before="-3.00 4.00 0.00", after="-3.00 4.00 0.00", start="-3.00 2.90 0.00", end="-3.00 5.60 0.00",
             **extra):
    return dict({"item_before": before, "item_after": after, "player_start": start, "player_end": end,
                 "shot_before": touch(d, "before.png"), "shot_after": touch(d, "after.png")}, **extra)


def control_obs(d, **extra):
    obs = dict(push_obs(d), player_spot="-3.00 4.00 0.00",
               spawn={"ref": "FF000800", "confirmed": True, "read": "-3.00 4.00 0.00"})
    obs.update(extra)
    return obs


def imp(read, applied=True, dv=1.5, magnitude=37.5):
    return {"dv": dv, "magnitude": magnitude, "cmd": "ApplyHavokImpulse 0 -0.707 0.707 37.5", "applied": applied,
            "read": read}


class ImpulseLadderTests(unittest.TestCase):
    def test_magnitudes_scale_with_mass_along_the_way_back_and_up(self):
        steps = tq.impulse_steps(25.0, 0)
        self.assertEqual([s["magnitude"] for s in steps], [37.5, 150.0, 600.0])
        self.assertEqual(steps[0]["cmd"], "ApplyHavokImpulse 0 -0.707 0.707 37.5")
        # heading 90 (walking east): the impulse goes back west and up
        self.assertEqual(tq.impulse_steps(10.0, 90, [1.5])[0]["cmd"], "ApplyHavokImpulse -0.707 0 0.707 15")
        ax = tq.impulse_axis(30.2)
        self.assertAlmostEqual(sum(x * x for x in ax), 1.0, places=2)

    def test_numbers_are_typed_without_trailing_zeros_or_minus_zero(self):
        self.assertEqual([tq._fmt(x) for x in (-0.0001, 1.5, 2.0, -0.7071, 600.0)], ["0", "1.5", "2", "-0.707", "600"])


class MovableJudgeTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def test_a_pack_on_a_desk_is_elevated_not_notmoved(self):
        # supervised_1011 0007 (2026-10-12): CigarettePack 0.83 m above the player's feet, on a desk (after.png); the
        # player stopped at the desk 0.67 m from it. It was judged FAIL NOTMOVED; nothing could have pushed it
        t = {"kind": "movable"}
        obs = push_obs(self.d, before="10.54 62.06 8.14", after="10.54 62.06 8.14", start="10.53 60.97 7.31",
                       end="10.45 61.40 7.31")
        v, c, d = tq.judge(t, obs, self.d)
        self.assertEqual((v, c), ("INCONCLUSIVE", "ELEVATED"), d)
        self.assertIn("0.83 m above the player's feet", d)
        self.assertIn("ELEVATED", tq.FINAL_INCONCLUSIVE)          # final, and never counted by the circuit breaker

    def test_a_book_on_a_bench_that_moved_is_still_a_pass(self):
        # supervised_1011 0015: the book lay 0.45 m up on a bench seat and moved 0.46 m when the player stepped up
        obs = push_obs(self.d, before="39.03 -66.76 -0.91", after="39.15 -67.09 -1.20", start="39.27 -65.69 -1.36",
                       end="39.10 -66.74 -0.68")
        self.assertEqual(tq.judge({"kind": "movable"}, obs, self.d)[:2], ("PASS", "PASS"))

    def test_movable_without_a_ladder_is_judged_as_before(self):
        obs = push_obs(self.d, before="44.92 87.04 11.02", after="44.92 87.04 11.02", start="44.37 86.09 10.97",
                       end="46.45 89.85 10.87")
        self.assertEqual(tq.judge({"kind": "movable"}, obs, self.d)[:2], ("FAIL", "NOTMOVED"))

    def test_movable_with_a_ladder(self):
        t = {"kind": "movable", "impulses": tq.impulse_steps(25.0, 30.2)}
        base = dict(before="44.92 87.04 11.02", after="44.92 87.04 11.02", start="44.37 86.09 10.97",
                    end="46.45 89.85 10.87")
        moved = push_obs(self.d, **base, impulses=[imp("44.92 87.04 11.02"), imp("44.60 86.50 11.02", dv=6.0, magnitude=150.0)])
        v, c, d = tq.judge(t, moved, self.d)
        self.assertEqual((v, c), ("PASS", "IMPULSE"), d)
        self.assertIn("player passed 0.02 m from it", d)
        self.assertIn("ApplyHavokImpulse 150.0 (dv 6.0 m/s, step 2) moved it 0.63 m", d)
        stuck = push_obs(self.d, **base, impulses=[imp("44.92 87.04 11.02")] * 3)
        self.assertEqual(tq.judge(t, stuck, self.d)[:2], ("FAIL", "STUCK"))
        cut = push_obs(self.d, **base, impulses=[imp("44.92 87.04 11.02"), imp(None, applied=False)])
        v, c, d = tq.judge(t, cut, self.d)
        self.assertEqual((v, c), ("INCONCLUSIVE", "IMPULSE"), d)
        self.assertIn("impulse 2 not applied", d)
        fell = push_obs(self.d, **base, impulses=[imp("44.92 87.04 8.00")])
        self.assertEqual(tq.judge(t, fell, self.d)[:2], ("FAIL", "ITEMFELL"))
        # an impulse moves an item on a desk, which the walk could never reach: a pass, not ELEVATED
        desk = push_obs(self.d, before="10.54 62.06 8.14", after="10.54 62.06 8.14", start="10.53 60.97 7.31",
                        end="10.45 61.40 7.31", impulses=[imp("10.54 61.70 8.14")])
        self.assertEqual(tq.judge(t, desk, self.d)[:2], ("PASS", "IMPULSE"))


class MovableControlJudgeTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.t = tq.movable_test(0, ITEM)

    def judge(self, obs, t=None):
        return tq.judge(t or self.t, obs, self.d)

    def test_walked_and_impulse(self):
        v, c, d = self.judge(control_obs(self.d, item_after="-3.00 6.10 0.00"))
        self.assertEqual((v, c), ("PASS", "WALKED"), d)
        self.assertIn("player passed 0.00 m from it", d)
        v, c, d = self.judge(control_obs(self.d, impulses=[imp("-3.00 3.55 0.00")]))
        self.assertEqual((v, c), ("PASS", "IMPULSE"), d)
        self.assertEqual(self.judge(control_obs(self.d, impulses=[imp("-3.00 4.00 0.00")] * 3))[:2], ("FAIL", "STUCK"))

    def test_preconditions(self):
        self.assertEqual(self.judge(control_obs(self.d, player_spot="10.0 10.0 0.0"))[:2], ("INCONCLUSIVE", "START"))
        self.assertEqual(self.judge(control_obs(self.d, player_spot=None))[:2], ("INCONCLUSIVE", "START"))
        bad = control_obs(self.d, spawn={"ref": "FF000800", "confirmed": False, "why": "GetIsID 0200CE2A read 0"})
        v, c, d = self.judge(bad)
        self.assertEqual((v, c), ("INCONCLUSIVE", "SPAWN"), d)
        self.assertIn("GetIsID 0200CE2A read 0", d)
        moving = control_obs(self.d, item_before="-3.00 4.40 0.00", item_after="-3.00 4.40 0.00")
        self.assertEqual(self.judge(moving)[:2], ("INCONCLUSIVE", "SETTLE"))
        self.assertEqual(self.judge(control_obs(self.d, item_after=None))[:2], ("INCONCLUSIVE", "UNREAD"))
        side = control_obs(self.d, player_start="0.00 2.90 0.00", player_end="0.00 5.60 0.00", impulses=[])
        self.assertEqual(self.judge(side)[:2], ("INCONCLUSIVE", "MISSED"))

    def test_set_mass(self):
        t = tq.movable_test(0, dict(ITEM, set_mass_kg=5, mass_probe=True))
        self.assertEqual(t["set_mass_cmd"], "SetRigidBodyMass 5")
        self.assertEqual(t["probe_cmd"], 'cf "ObjectReference.GetMass"')
        self.assertEqual(t["impulses"][0]["magnitude"], 7.5)          # the ladder is for the mass set
        ok = control_obs(self.d, item_after="-3.00 6.10 0.00",
                         set_mass={"typed": True, "ocr": "Clear Console SetRigidBodyMass 5"})
        v, c, d = self.judge(ok, t)
        self.assertEqual((v, c), ("PASS", "WALKED"), d)
        self.assertIn("SetRigidBodyMass 5 typed; its effect is not read back", d)
        self.assertEqual(self.judge(control_obs(self.d, set_mass={"typed": False}), t)[:2], ("INCONCLUSIVE", "SETMASS"))
        refused = control_obs(self.d, set_mass={"typed": True, "ocr": 'Missing reference Clear Console SetRigidBodyMass 5 '
                                                                     'Script command "SetRigidBodyMass" not found.'})
        self.assertEqual(self.judge(refused, t)[:2], ("INCONCLUSIVE", "SETMASS"))
        # a refusal printed before this session's ClearConsole belongs to an older session
        old = control_obs(self.d, item_after="-3.00 6.10 0.00",
                          set_mass={"typed": True, "ocr": "Missing reference Clear Console SetRigidBodyMass 5"})
        self.assertEqual(self.judge(old, t)[:2], ("PASS", "WALKED"))


class MovablePlanTests(unittest.TestCase):
    def test_plan_entry_fields(self):
        t = tq.movable_test(3, dict(ITEM, heading=90, fresh=True, expect="PASS IMPULSE", basis="b"))
        self.assertEqual(t["id"], "0003_movable_control_C_burntbook")
        self.assertEqual((t["kind"], t["cell"], t["base"], t["travel"]), ("movable_control", "", "0200CE2A", "coc QASmoke"))
        self.assertEqual(t["park"], [-6.0, 4.0, 0.0])                 # 3 m behind the spot, against the walk
        self.assertEqual((t["stand_m"], t["walk_ms"], t["moved_m"]), (1.1, 900, tq.MOVE_M))
        self.assertEqual(len(t["impulses"]), 3)
        self.assertTrue(t["fresh"])
        self.assertEqual((t["expect"], t["basis"]), ("PASS IMPULSE", "b"))
        self.assertNotIn("set_mass_cmd", t)
        self.assertEqual(tq.movable_test(0, dict(ITEM, impulse_dv=[]))["impulses"], [])

    def test_bad_entries_stop_the_planning(self):
        for bad in ({"travel": "player.moveto 02000800"}, {"base": "0200CE2A 1"}, {"base": None},
                    {"base_edid": "FO4Port_BurntBook01"}, {"spot": [1, 2]}, {"heading": 400}, {"mass_kg": 0},
                    {"set_mass_kg": 5000}, {"impulse_dv": [500]}, {"park_m": 1.0}, {"typo": 1}):
            with self.subTest(bad=bad), self.assertRaises(SystemExit):
                tq.movable_test(0, dict(ITEM, **bad))

    def test_a_converted_item_by_its_editor_id(self):
        formids = {"MSTT:FO4Port_BurntBook01": 0xCE2A, "STAT:FO4Port_BurntBook01": 0xDEB}
        items = {"meshes\\props\\burntbook01.nif": {"editor_id": "FO4Port_BurntBook01", "source": "meshes\\Props\\BurntBook01.nif",
                                                     "movable": {"mass_kg": 25.0}}}
        w = {"label": "C_book", "travel": "coc QASmoke", "base_edid": "FO4Port_BurntBook01", "spot": [0, 0, 0]}
        t = tq.movable_test(0, w, formids, items, "02")
        self.assertEqual((t["base"], t["mass_kg"]), ("0200CE2A", 25.0))
        self.assertEqual(t["model"], "meshes\\Props\\BurntBook01.nif")
        with self.assertRaises(SystemExit):                            # not in the build
            tq.movable_test(0, dict(w, base_edid="FO4Port_Nothing"), formids, items, "02")

    def test_plan_movable_writes_a_queue_that_needs_the_impulse_runner(self):
        d = tempfile.mkdtemp()
        staging, exp, out = (os.path.join(d, x) for x in ("staging", "exp", "queue"))
        os.makedirs(staging)
        os.makedirs(exp)
        with open(os.path.join(staging, "FO4Port.esm"), "wb") as f:
            f.write(b"TES4")
        jdump({"MSTT:FO4Port_BurntBook01": 0xCE2A}, os.path.join(staging, "formids.json"))
        jdump({"items": [{"editor_id": "FO4Port_BurntBook01", "source": "meshes\\Props\\BurntBook01.nif",
                          "movable": {"mass_kg": 25.0}}]}, os.path.join(staging, "manifest.json"))
        jdump([dict(ITEM, label="V_x", base="002A0D5B", mass_kg=10.0),
               {"label": "C_book", "travel": "coc QASmoke", "base_edid": "FO4Port_BurntBook01", "spot": [0, 0, 0]}],
              os.path.join(exp, "plan.json"))
        a = SimpleNamespace(staging=staging, exp_dir=exp, out=out, launch_cell="Vault111Cryo", plugin_index="02", only=0,
                            fresh=True)
        tq.plan_movable(a)
        q = jload(os.path.join(out, "queue.json"))
        self.assertEqual([t["base"] for t in q["tests"]], ["002A0D5B", "0200CE2A"])
        self.assertTrue(all(t["fresh"] for t in q["tests"]))
        self.assertEqual(q["needs"], ["impulse"])
        self.assertEqual(q["pre_launch"][-2:], ["check", "impulse"])          # the runner's own runner_features.py
        self.assertEqual(q["launch_cell"], "Vault111Cryo")
        jdump([dict(ITEM, label="same"), dict(ITEM, label="same")], os.path.join(exp, "plan.json"))
        with self.assertRaises(SystemExit):
            tq.plan_movable(a)


class FakeControls:
    last_sent_tick = None

    def stop_file(self):
        return None

    def guardian_mode(self):
        return "running"

    def idle_s(self):
        return 10 ** 6

    def foreign_input(self):
        return False

    def mark_sent(self):
        pass

    def game_in_front(self):
        return True

    def game_pid(self):
        return 42

    def owned_pid(self):
        return 42


class ElevatedRunTests(unittest.TestCase):
    def test_items_on_furniture_are_final_and_never_trip_the_breaker(self):
        # batch_full (2026-10-12): six movable tests in a row without a decision switched the kind off and about 610
        # movable tests were skipped. An item on a desk is ELEVATED: final at once, not counted
        d = tempfile.mkdtemp()
        tests = [{"id": f"{k:04d}_movable", "kind": "movable", "cell": "C", "ref": f"r{k}", "model": "m.nif"}
                 for k in range(tq.BREAKER + 2)]
        jdump({"build_id": "abcd1234", "commit": "0" * 40, "staging": d, "plugin_sha256": "x", "save": "s",
               "plugin_index": "02", "hours": [[0, 24]], "tests": tests}, os.path.join(d, "queue.json"))

        def step(t, o):
            jdump(push_obs(o, before="10.54 62.06 8.14", after="10.54 62.06 8.14", start="10.53 60.97 7.31",
                           end="10.45 61.40 7.31"), os.path.join(o, "obs.json"))
            return 0
        a = SimpleNamespace(max_tests=10 ** 6, max_hours=1.0, min_idle=900, max_attempts=2, max_relaunch=3,
                            wait_for_idle=False, refocus=False, dry_run=False, starfield="")
        r = tq.Runner(d, a, ctl=FakeControls(), step=step)
        r.session, r.cell, r._ps = True, "C", (lambda *x, **k: (0, ""))
        r.run()
        st = jload(os.path.join(d, "state.json"))
        self.assertEqual({v["class"] for v in st["done"].values()}, {"ELEVATED"})
        self.assertEqual(set(st["attempts"].values()), {1})               # never retried
        self.assertFalse(st["breaker"]["movable"]["open"])


class RunnerSupportTests(unittest.TestCase):
    def test_features(self):
        self.assertIn("impulse", runner_features.FEATURES)
        self.assertEqual(runner_features.needs([tq.movable_test(0, ITEM)]), ["impulse"])
        self.assertEqual(runner_features.needs([{"kind": "movable"}]), [])
        self.assertEqual(runner_features.needs([{"kind": "movable", "impulses": tq.impulse_steps(1, 0)}]), ["impulse"])

    def test_step_timeouts_cover_the_ladder(self):
        t = tq.movable_test(0, dict(ITEM, set_mass_kg=5, mass_probe=True))
        self.assertGreater(tq.step_timeout(t), 1500)
        self.assertGreater(tq.step_timeout(t), tq.step_timeout(dict(t, impulses=[])) + 3 * 4 * tq.NPC_SESSION_S)
        self.assertEqual(tq.step_timeout({"kind": "movable"}), 300)
        self.assertGreater(tq.step_timeout({"kind": "movable", "impulses": tq.impulse_steps(1, 0)}), 900)

    def test_qstep_has_the_kind(self):
        with open(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("'movable_control' {", src)
        self.assertIn("Push-Impulses", src)

    def test_the_report_names_the_pass_class_in_expectations(self):
        d = tempfile.mkdtemp()
        tests = [dict(tq.movable_test(k, dict(ITEM, label=f"i{k}", expect=e)), id=f"{k:04d}_i")
                 for k, e in enumerate(("PASS IMPULSE", "PASS WALKED"))]
        jdump({"build_id": "abcd1234", "commit": "0" * 40, "tests": tests}, os.path.join(d, "queue.json"))
        with open(os.path.join(d, "results.jsonl"), "w") as f:
            for t in tests:
                f.write(json.dumps({"id": t["id"], "kind": t["kind"], "cell": "", "model": t["model"],
                                    "verdict": "PASS", "class": "IMPULSE", "detail": "x", "dir": ""}) + "\n")
        jdump({"done": {t["id"]: {} for t in tests}}, os.path.join(d, "state.json"))
        rep = tq.write_report(d)
        self.assertEqual([(e["result"], e["expect"]) for e in rep["expectations"]],
                         [("PASS IMPULSE", "PASS IMPULSE"), ("PASS IMPULSE", "PASS WALKED")])
        with open(os.path.join(d, "report.md"), encoding="utf-8") as f:
            md = f.read()
        self.assertIn("| movable_control | 2 | 0 | 0 |", md)
        self.assertIn("| 0000_i | PASS IMPULSE | PASS IMPULSE | yes |", md)
        self.assertIn("| 0001_i | PASS WALKED | PASS IMPULSE | no |", md)


if __name__ == "__main__":
    unittest.main()
