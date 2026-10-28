"""python -m fo4sf.combined through main(argv): synthetic packs and plugins in temp dirs, no game data."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # sibling test module below

from fo4sf.combined import __main__ as cli  # noqa: E402
from fo4sf.combined import balance, news, present, sim  # noqa: E402
from fo4sf.combined.fixtures import REGION_1, REGION_2  # noqa: E402
from fo4sf.combined.model import WorldState  # noqa: E402
from test_combined_seed import edid, grup, plugin, rec  # noqa: E402


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.r1 = self.write("r1.json", REGION_1)
        self.r2 = self.write("r2.json", REGION_2)

    def write(self, name, obj):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        return path

    def test_demo_prints_summary(self):
        code, out, _ = run(["demo", "--seed", "3", "--days", "10"])
        self.assertEqual(code, 0)
        s = json.loads(out)
        self.assertEqual(s["hour"], 240)
        self.assertIn("river_town", s["settlements"])
        self.assertEqual(s["holders"]["story_vault"], "settlers")
        self.assertIsInstance(s["events"], dict)

    def test_simulate_two_packs_saves_state(self):
        state = os.path.join(self.dir, "state.json")
        code, out, _ = run(["simulate", "--pack", self.r1, "--pack", self.r2, "--seed", "5", "--days", "20",
                            "--out", state])
        self.assertEqual(code, 0)
        with open(state, encoding="utf-8") as f:
            ws = WorldState.from_json(f.read())
        self.assertEqual((ws.seed, ws.hour), (5, 480))
        self.assertEqual(json.loads(out)["holders"], {k: p.holder for k, p in sorted(ws.places.items())})

    def test_resume_replays_exactly(self):
        a, b = os.path.join(self.dir, "a.json"), os.path.join(self.dir, "b.json")
        self.assertEqual(run(["simulate", "--pack", self.r1, "--seed", "9", "--days", "30", "--out", a])[0], 0)
        self.assertEqual(run(["simulate", "--pack", self.r1, "--seed", "9", "--days", "10", "--out", b])[0], 0)
        code, out, _ = run(["simulate", "--resume", b, "--days", "20"])
        self.assertEqual(code, 0)
        with open(a, encoding="utf-8") as f:
            whole = cli.summary(WorldState.from_json(f.read()))
        self.assertEqual(json.loads(out), whole)

    def test_resume_can_add_a_pack(self):
        b = os.path.join(self.dir, "b.json")
        run(["simulate", "--pack", self.r1, "--seed", "9", "--days", "1", "--out", b])
        code, out, _ = run(["simulate", "--resume", b, "--pack", self.r2, "--days", "1"])
        self.assertEqual(code, 0)
        self.assertIn("river_town", json.loads(out)["holders"])

    def test_invalid_pack_is_an_error_not_a_traceback(self):
        bad = self.write("bad.json", {"places": [{"id": "x", "region": "R", "kind": "castle"}]})
        code, _, err = run(["simulate", "--pack", bad, "--days", "1"])
        self.assertEqual(code, 1)
        self.assertIn("kind 'castle'", err)

    def test_simulate_without_places(self):
        code, _, err = run(["simulate", "--days", "1"])
        self.assertEqual(code, 2)
        self.assertIn("no places", err)

    def test_seed_writes_draft_and_report(self):
        esm = os.path.join(self.dir, "Tiny.esm")
        plugin(esm, [], [grup(b"LCTN", [rec(b"LCTN", 0x40, [edid("TestSpot")])])])
        out_dir = os.path.join(self.dir, "out")
        code, out, _ = run(["seed", out_dir, esm])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["locations"], 1)
        self.assertEqual(sorted(os.listdir(out_dir)), ["commonwealth_seed.draft.json", "seed_report.json"])

    def test_seed_rejects_non_plugin(self):
        junk = os.path.join(self.dir, "junk.txt")
        with open(junk, "w") as f:
            f.write("x" * 40)
        code, _, err = run(["seed", os.path.join(self.dir, "out"), junk])
        self.assertEqual(code, 1)
        self.assertIn("not a plugin", err)

    # --- M3: balance, news, present ---------------------------------------------------------------

    def test_balance_on_fixtures_prints_aggregate_and_exits_0(self):
        code, out, _ = run(["balance", "--seeds", "3", "--days", "10"])
        self.assertEqual(code, 0)
        r = json.loads(out)
        self.assertEqual((r["seeds"], r["days"], r["broken"], r["overrides"]), (3, 10, [], {}))
        self.assertEqual(r["aggregate"]["seeds"], 3)
        self.assertEqual(r["aggregate"]["story_lock_violations"], 0)
        self.assertEqual(r["aggregate"], balance.sweep([REGION_1, REGION_2], range(3), 10)["aggregate"])

    def test_balance_set_override_can_break_a_bound_and_is_restored(self):
        code, out, _ = run(["balance", "--seeds", "2", "--days", "10", "--set", "sim.ATTACK_CHANCE_PER_AGGRESSION=0"])
        self.assertEqual(code, 1)
        r = json.loads(out)
        self.assertEqual(r["overrides"], {"sim.ATTACK_CHANCE_PER_AGGRESSION": 0})
        self.assertEqual(r["aggregate"]["attacks_per_day"], 0.0)
        self.assertTrue(any(line.startswith("attacks_per_day") for line in r["broken"]), r["broken"])
        self.assertEqual(sim.ATTACK_CHANCE_PER_AGGRESSION, 0.25)

    def test_balance_bounds_choice_names_the_yardstick(self):
        """28 Oct: a real Commonwealth pack read against the 11-place fixture bounds looked broken; --bounds scale
        judges it per place and per faction instead, and the output says which bounds it used."""
        code, out, _ = run(["balance", "--seeds", "2", "--days", "10"])
        self.assertEqual((code, json.loads(out)["bounds"]), (0, "fixtures"))
        code, out, _ = run(["balance", "--seeds", "2", "--days", "10", "--bounds", "scale"])
        r = json.loads(out)
        self.assertEqual(r["bounds"], "scale")
        self.assertEqual(r["broken"], balance.check(r["aggregate"], balance.SCALE_BOUNDS))
        self.assertEqual(code, 1 if r["broken"] else 0)
        self.assertTrue(all(line.split(":")[0] in balance.SCALE_BOUNDS for line in r["broken"]), r["broken"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["balance", "--seeds", "1", "--days", "1", "--bounds", "nope"])

    def test_balance_takes_packs_and_rejects_bad_set(self):
        code, out, _ = run(["balance", "--seeds", "2", "--days", "5", "--pack", self.r1, "--pack", self.r2])
        self.assertEqual(code, 0)
        self.assertIn("slavers", json.loads(out)["aggregate"]["home_only_share"])
        for bad in ("NO_SUCH=1", "UPKEEP_PER_PLACE", "sim.UPKEEP_PER_PLACE=abc", "sim.UPKEEP_PER_PLACE=",
                    'sim.UPKEEP_PER_PLACE="2"', "present.RADIUS_HOURS=0"):
            code, _, err = run(["balance", "--seeds", "1", "--days", "1", "--set", bad])
            self.assertEqual(code, 1, bad)
            self.assertTrue(err.startswith("error:"), err)
            self.assertEqual(sim.UPKEEP_PER_PLACE, 1, bad)

    def test_news_from_resumed_state(self):
        state = os.path.join(self.dir, "state.json")
        run(["simulate", "--pack", self.r1, "--seed", "3", "--days", "20", "--out", state])
        code, out, _ = run(["news", "--resume", state, "--place", "market"])
        self.assertEqual(code, 0)
        with open(state, encoding="utf-8") as f:
            ws = WorldState.from_json(f.read())
        self.assertEqual(out.rstrip("\n"), news.terminal_page(ws, "market"))
        self.assertTrue(out.startswith("market news, Day 21, 00:00"))

    def test_news_from_packs_alone_has_no_news_yet(self):
        code, out, _ = run(["news", "--pack", self.r1, "--pack", self.r2, "--place", "river_town"])
        self.assertEqual(code, 0)
        self.assertIn("No news has reached river town.", out)

    def test_present_from_resumed_state(self):
        state = os.path.join(self.dir, "state.json")
        run(["simulate", "--pack", self.r1, "--seed", "3", "--days", "20", "--out", state])
        code, out, _ = run(["present", "--resume", state, "--place", "market"])
        self.assertEqual(code, 0)
        with open(state, encoding="utf-8") as f:
            ws = WorldState.from_json(f.read())
        self.assertEqual(json.loads(out), present.plan(ws, "market").to_dict())
        self.assertEqual(json.loads(out)["centre"], "market")

    def test_news_and_present_refuse_unknown_place_or_empty_world(self):
        for cmd in ("news", "present"):
            code, _, err = run([cmd, "--pack", self.r1, "--place", "nowhere"])
            self.assertEqual(code, 2)
            self.assertIn("unknown place 'nowhere'", err)
            code, _, err = run([cmd, "--place", "market"])
            self.assertEqual(code, 2)
            self.assertIn("no places", err)


if __name__ == "__main__":
    unittest.main()
