"""Movable items in the queued runner (scripts/game/testqueue.py): the walk, then the ApplyHavokImpulse ladder. Only the
walk passes a movable test (an impulse that moves the build's item is a diagnostic: FAIL NOTMOVED when the walk reached
it); items on furniture the walk did not reach are ELEVATED, an item the walk passed through is NOTMOVED however high it
lies; a SetRigidBodyMass test is judged only on a GetMass reading of the mass set; movable_control plans (an item
placed in a vanilla cell) are validated before anything can be typed. Synthetic data; no game, no PowerShell
(tests/test_qstep_sandbox.py runs the step itself)."""
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
        self.assertIn("0.83 m above the player's feet (on furniture) and the walk came no closer than 0.67 m", d)
        self.assertIn("ELEVATED", tq.FINAL_INCONCLUSIVE)          # final, and never counted by the circuit breaker

    def test_an_item_the_walk_passed_through_is_notmoved_however_high_it_lies(self):
        # batch_full 0100 (BobbyPinBox 1015BB, verifier of PR #110): 0.81 m above the feet at the stand point, but the
        # walk passed 0.26 m from it and the player rose 0.28 m on the way (0.53 m below the item at the end): inside
        # the capsule's reach and height. It moved 0.000 m: FAIL NOTMOVED, not a final INCONCLUSIVE ELEVATED
        obs = push_obs(self.d, before="33.62 68.45 11.78", after="33.62 68.45 11.78", start="32.94 67.36 10.97",
                       end="34.31 71.12 11.25")
        v, c, d = tq.judge({"kind": "movable"}, obs, self.d)
        self.assertEqual((v, c), ("FAIL", "NOTMOVED"), d)
        self.assertIn("player passed 0.27 m from it", d)          # 0.26 m in the verifier's figure
        # the same item 0.6 m above the feet, the walk passing 0.3 m from it without climbing: still within contact
        obs = push_obs(self.d, before="0.30 1.00 0.60", after="0.30 1.00 0.60", start="0.00 0.00 0.00",
                       end="0.00 2.50 0.00")
        self.assertEqual(tq.judge({"kind": "movable"}, obs, self.d)[:2], ("FAIL", "NOTMOVED"))
        # a player who climbs onto the bench and passes over the item: its height above the start no longer counts
        obs = push_obs(self.d, before="0.05 1.00 0.70", after="0.05 1.00 0.70", start="0.00 0.00 0.00",
                       end="0.00 1.60 0.66")
        self.assertEqual(tq.judge({"kind": "movable"}, obs, self.d)[:2], ("FAIL", "NOTMOVED"))

    def test_an_item_above_the_head_or_out_of_contact_on_furniture_is_elevated(self):
        # the walk under a shelf 2 m up: the capsule never touches it
        obs = push_obs(self.d, before="0.05 1.00 2.00", after="0.05 1.00 2.00", start="0.00 0.00 0.00",
                       end="0.00 2.50 0.00")
        v, c, d = tq.judge({"kind": "movable"}, obs, self.d)
        self.assertEqual((v, c), ("INCONCLUSIVE", "ELEVATED"), d)
        self.assertIn("above the player's head", d)
        # 0.55 m up (between the bench that was climbed and the desk) and the walk stopped 0.6 m short of it
        obs = push_obs(self.d, before="0.00 1.20 0.55", after="0.00 1.20 0.55", start="0.00 0.00 0.00",
                       end="0.00 0.60 0.00")
        self.assertEqual(tq.judge({"kind": "movable"}, obs, self.d)[:2], ("INCONCLUSIVE", "ELEVATED"))

    def test_an_item_on_the_players_floor_the_walk_stopped_short_of_is_missed(self):
        # batch_full 0098 (BobbyPinBox 100164): the player was teleported onto the item's own surface (item z 11.78,
        # player z 11.77), moved 0.17 m and stopped 1.45 m short of it: blocked by something else, not elevation
        obs = push_obs(self.d, before="20.00 31.62 11.78", after="20.00 31.62 11.78", start="20.00 30.00 11.77",
                       end="20.00 30.17 11.77")
        v, c, d = tq.judge({"kind": "movable"}, obs, self.d)
        self.assertEqual((v, c), ("INCONCLUSIVE", "MISSED"), d)
        self.assertIn("no closer than 1.45 m", d)

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
        # the walk passed over the book and did not move it; the second impulse did. The player still cannot push it:
        # FAIL NOTMOVED (the ladder's magnitudes are mass x dv, so they move a heavy item as easily as a light one and
        # can never show that the mass stops the player; verifier of PR #110)
        moved = push_obs(self.d, **base, impulses=[imp("44.92 87.04 11.02"), imp("44.60 86.50 11.02", dv=6.0, magnitude=150.0)])
        v, c, d = tq.judge(t, moved, self.d)
        self.assertEqual((v, c), ("FAIL", "NOTMOVED"), d)
        self.assertIn("player passed 0.02 m from it", d)
        self.assertIn("ApplyHavokImpulse 150.0 (dv 6.0 m/s, step 2) then moved it 0.63 m: the body is simulated", d)
        stuck = push_obs(self.d, **base, impulses=[imp("44.92 87.04 11.02")] * 3)
        self.assertEqual(tq.judge(t, stuck, self.d)[:2], ("FAIL", "STUCK"))
        # a ladder that did not finish leaves the walk's failure as it is
        cut = push_obs(self.d, **base, impulses=[imp("44.92 87.04 11.02"), imp(None, applied=False)])
        v, c, d = tq.judge(t, cut, self.d)
        self.assertEqual((v, c), ("FAIL", "NOTMOVED"), d)
        self.assertIn("the impulse ladder did not finish: impulse 2 not applied", d)
        fell = push_obs(self.d, **base, impulses=[imp("44.92 87.04 8.00")])
        self.assertEqual(tq.judge(t, fell, self.d)[:2], ("FAIL", "ITEMFELL"))
        # an impulse moves an item on a desk the walk did not reach: ELEVATED (no PASS without the walk), the body noted
        desk = push_obs(self.d, before="10.54 62.06 8.14", after="10.54 62.06 8.14", start="10.53 60.97 7.31",
                        end="10.45 61.40 7.31", impulses=[imp("10.54 61.70 8.14")])
        v, c, d = tq.judge(t, desk, self.d)
        self.assertEqual((v, c), ("INCONCLUSIVE", "ELEVATED"), d)
        self.assertIn("the body is simulated", d)
        # out of reach on the floor: MISSED, with what the impulse showed
        far = push_obs(self.d, **base, impulses=[imp("44.60 86.50 11.02")])
        far.update(player_start="40.00 80.00 10.97", player_end="40.00 81.00 10.97")
        v, c, d = tq.judge(t, far, self.d)
        self.assertEqual((v, c), ("INCONCLUSIVE", "MISSED"), d)
        self.assertIn("the body is simulated", d)

    def test_no_movable_result_is_a_pass_without_the_walk(self):
        # whatever the ladder did, a movable test whose walk left the item in place is never PASS
        t = {"kind": "movable", "impulses": tq.impulse_steps(50.0, 0)}
        for start, end in (("0.00 -1.10 0.00", "0.00 1.50 0.00"), ("0.00 -1.10 0.00", "0.00 -0.40 0.00"),
                           ("5.00 -1.10 0.00", "5.00 1.50 0.00")):
            for ladder in ([imp("0.00 -0.50 0.00")], [imp("0.00 0.00 0.00"), imp("0.00 -2.00 0.00")]):
                obs = push_obs(self.d, before="0.00 0.00 0.00", after="0.00 0.00 0.00", start=start, end=end,
                               impulses=ladder)
                v, c, d = tq.judge(t, obs, self.d)
                self.assertNotEqual(v, "PASS", d)


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
        self.assertIn("player passed 0.00 m from it (walked 2.7 m) but it moved 0.000 m", d)
        self.assertEqual(self.judge(control_obs(self.d, impulses=[imp("-3.00 4.00 0.00")] * 3))[:2], ("FAIL", "STUCK"))

    def test_impulse_after_a_walk_that_missed_the_item_is_not_a_pass(self):
        # PASS IMPULSE stands for "walked into or over it, not pushed, an impulse moved it"; a walk that never came
        # within reach_m says nothing about pushing
        side = control_obs(self.d, player_start="-1.50 2.90 0.00", player_end="-1.50 5.60 0.00",
                           impulses=[imp("-3.00 3.55 0.00")])
        v, c, d = self.judge(side)
        self.assertEqual((v, c), ("INCONCLUSIVE", "MISSED"), d)
        self.assertIn("the body is simulated", d)

    def test_preconditions(self):
        self.assertEqual(self.judge(control_obs(self.d, player_spot="10.0 10.0 0.0"))[:2], ("INCONCLUSIVE", "START"))
        self.assertEqual(self.judge(control_obs(self.d, player_spot=None))[:2], ("INCONCLUSIVE", "START"))
        # the player at the spot's x y but not on the floor planned there (verifier of PR #110: the QASmoke lanes are
        # not shown to be open floor): on top of something, or fallen below it
        for z in ("1.20", "-2.00"):
            v, c, d = self.judge(control_obs(self.d, player_spot=f"-3.00 4.00 {z}"))
            self.assertEqual((v, c), ("INCONCLUSIVE", "START"), d)
            self.assertIn("from the spot's height", d)
        # the stand point on another floor
        v, c, d = self.judge(control_obs(self.d, player_start="-3.00 2.90 0.90"))
        self.assertEqual((v, c), ("INCONCLUSIVE", "START"), d)
        # the item came to rest on something above the spot (or fell below it)
        up = control_obs(self.d, spawn={"ref": "FF000800", "confirmed": True, "read": "-3.00 4.00 0.90"},
                         item_before="-3.00 4.00 0.90", item_after="-3.00 4.00 0.90")
        v, c, d = self.judge(up)
        self.assertEqual((v, c), ("INCONCLUSIVE", "SPAWN"), d)
        self.assertIn("not on the floor there", d)
        # a tall item's origin a little above the floor is fine
        ok = control_obs(self.d, spawn={"ref": "FF000800", "confirmed": True, "read": "-3.00 4.00 0.30"},
                         item_before="-3.00 4.00 0.30", item_after="-3.00 6.10 0.30")
        self.assertEqual(self.judge(ok)[:2], ("PASS", "WALKED"))
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
        t = tq.movable_test(0, dict(ITEM, set_mass_kg=5))
        self.assertEqual(t["set_mass_cmd"], "SetRigidBodyMass 5")
        self.assertEqual(t["probe_cmd"], 'cf "ObjectReference.GetMass"')   # always with set_mass_kg: its reading is judged
        self.assertEqual(t["mass_wait_ms"], tq.MASS_WAIT_MS)
        self.assertEqual(t["impulses"][0]["magnitude"], 7.5)          # the ladder is for the mass set
        with self.assertRaises(SystemExit):                            # a set mass that is never read back
            tq.movable_test(0, dict(ITEM, set_mass_kg=5, mass_probe=False))
        typed = {"typed": True, "ocr": "Clear Console SetRigidBodyMass 5"}
        probe = {"before": 'Clear Console cf "ObjectReference.GetMass" GetMass > > 25.00',
                 "after": 'GetMass > > 25.00 Clear Console cf "ObjectReference.GetMass" GetMass > > 5.00'}
        ok = control_obs(self.d, item_after="-3.00 6.10 0.00", set_mass=typed, mass_probe=probe)
        v, c, d = self.judge(ok, t)
        self.assertEqual((v, c), ("PASS", "WALKED"), d)
        self.assertIn("[GetMass 5 kg after SetRigidBodyMass 5 (before: 25 kg)]", d)
        self.assertEqual(self.judge(control_obs(self.d, set_mass={"typed": False}), t)[:2], ("INCONCLUSIVE", "SETMASS"))
        refused = control_obs(self.d, set_mass={"typed": True, "ocr": 'Missing reference Clear Console SetRigidBodyMass 5 '
                                                                     'Script command "SetRigidBodyMass" not found.'})
        self.assertEqual(self.judge(refused, t)[:2], ("INCONCLUSIVE", "SETMASS"))
        # a refusal printed before this session's ClearConsole belongs to an older session
        old = control_obs(self.d, item_after="-3.00 6.10 0.00", mass_probe=probe,
                          set_mass={"typed": True, "ocr": "Missing reference Clear Console SetRigidBodyMass 5"})
        self.assertEqual(self.judge(old, t)[:2], ("PASS", "WALKED"))

    def test_a_mass_not_read_back_is_inconclusive(self):
        # verifier of PR #110: if SetRigidBodyMass does nothing, the 5 kg copy behaves as the original and the queue
        # would read "thinness, not mass"; such a test is judged only when GetMass reads the mass set
        t = tq.movable_test(0, dict(ITEM, set_mass_kg=5))
        typed = {"typed": True, "ocr": "Clear Console SetRigidBodyMass 5"}
        walked = dict(item_after="-3.00 6.10 0.00", set_mass=typed)
        for probe, why in (
                (None, "not captured"),
                ({"before": 'Clear Console cf "ObjectReference.GetMass" GetMass > > 25.00'}, "not captured"),
                ({"after_note": "the item was not selected again"}, "not selected again"),
                ({"after": 'Clear Console cf "ObjectReference.GetMass"'}, "no number"),
                ({"after": "Clear Console prid FF000800"}, "echo was not read"),
                ({"after": 'Clear Console cf "ObjectReference.GetMass" GetMass > > 5.00 6.00'}, "several numbers")):
            with self.subTest(why=why):
                v, c, d = self.judge(control_obs(self.d, mass_probe=probe, **walked), t)
                self.assertEqual((v, c), ("INCONCLUSIVE", "MASS"), d)
                self.assertIn(why, d)
        # read, but the mass did not change: nothing about mass can be said, whether or not the walk moved it
        same = {"before": 'Clear Console cf "ObjectReference.GetMass" GetMass > > 25.00',
                "after": 'Clear Console cf "ObjectReference.GetMass" GetMass > > 25.00'}
        for after in ("-3.00 6.10 0.00", "-3.00 4.00 0.00"):
            v, c, d = self.judge(control_obs(self.d, mass_probe=same, set_mass=typed, item_after=after,
                                             impulses=[imp("-3.00 3.55 0.00")]), t)
            self.assertEqual((v, c), ("INCONCLUSIVE", "MASS"), d)
            self.assertIn("GetMass read 25 kg after SetRigidBodyMass 5 (before: 25 kg): the mass set did not take", d)
        self.assertNotIn("MASS", tq.FINAL_INCONCLUSIVE)               # retried: an OCR miss can read on the next try

    def test_a_mass_the_console_cannot_read_judges_only_a_move(self):
        # movable_1019c (2026-10-18, verified): cf "ObjectReference.GetMass" answers "No script named ObjectReference is
        # attached to the object", so no reading will ever come. A move stands (the set mass can only have made the
        # body lighter or left it as it was); no move stays INCONCLUSIVE MASS (an unchanged mass reads the same)
        t = tq.movable_test(0, dict(ITEM, set_mass_kg=5))
        typed = {"typed": True, "ocr": "Clear Console SetRigidBodyMass 5"}
        nos = {"after": 'Clear Console cf "ObjectReference.GetMass" No script named ObjectReference is attached to the '
                        'object'}
        v, c, d = self.judge(control_obs(self.d, mass_probe=nos, set_mass=typed, item_after="-3.00 6.10 0.00"), t)
        self.assertEqual((v, c), ("PASS", "WALKED"), d)
        self.assertIn("[mass not read back: GetMass is not reachable from the console", d)
        v, c, d = self.judge(control_obs(self.d, mass_probe=nos, set_mass=typed, impulses=[imp("-3.00 3.55 0.00")]), t)
        self.assertEqual((v, c), ("PASS", "IMPULSE"), d)
        for obs in (control_obs(self.d, mass_probe=nos, set_mass=typed),
                    control_obs(self.d, mass_probe=nos, set_mass=typed, impulses=[imp("-3.00 4.00 0.00")] * 3)):
            v, c, d = self.judge(obs, t)
            self.assertEqual((v, c), ("INCONCLUSIVE", "MASS"), d)
            self.assertIn("its mass not read back: a mass that did not take reads the same", d)
        # Codex on #343 at 069d525: the exception needs this session's GetMass echo, then ObjectReference's refusal
        self.assertTrue(tq.unreadable_mass(nos["after"]))
        for other in ('No script named X Clear Console cf "ObjectReference.GetMass"',          # an older session's
                      'Clear Console cf "Actor.PathToReference" No script named Actor is attached to the object',
                      "No script named ObjectReference is attached to the object",           # no echo, no session
                      "Clear Console No script named ObjectReference is attached to the object"):
            with self.subTest(other=other):
                self.assertFalse(tq.unreadable_mass(other))
                v, c, d = self.judge(control_obs(self.d, mass_probe={"after": other}, set_mass=typed,
                                                 item_after="-3.00 6.10 0.00"), t)
                self.assertEqual((v, c), ("INCONCLUSIVE", "MASS"), d)
        # an item still settling before the walk is SETTLE before any mass rule (Codex's first case)
        drift = control_obs(self.d, mass_probe=nos, set_mass=typed, item_before="-3.00 4.50 0.00",
                            item_after="-3.00 6.10 0.00")
        self.assertEqual(self.judge(drift, t)[:2], ("INCONCLUSIVE", "SETTLE"))

    def test_mass_read(self):
        self.assertEqual(tq.mass_read('Clear Console cf "ObjectReference.GetMass" GetMass >> 5.00'), (5.0, ""))
        self.assertEqual(tq.mass_read('ClearConsole cf "ObjectReference.GetMass" 12,5')[0], 12.5)
        self.assertEqual(tq.mass_read('cf "ObjectReference.GetMass" GetMass > > 5.00 GetMass > > 5.00')[0], 5.0)
        self.assertIsNone(tq.mass_read("")[0])
        self.assertIsNone(tq.mass_read('Clear Console cf "ObjectReference.GetMass" Script command not found 5')[0])
        self.assertTrue(tq.mass_ok(5.1, 5.0) and tq.mass_ok(4.8, 5.0) and not tq.mass_ok(5.4, 5.0))
        self.assertTrue(tq.mass_ok(19.2, 20.0) and not tq.mass_ok(18.9, 20.0) and not tq.mass_ok(None, 5.0))


class ImpulseControlTests(unittest.TestCase):
    # movable_1019c (2026-10-18): two converted items FAIL STUCK, but no impulse had ever been typed on a vanilla item
    # (the V_ controls moved on the walk, so their ladder never ran). impulse_control runs it anyway: the positive
    # control a STUCK is read against
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.t = tq.movable_test(0, dict(ITEM, label="V_trashbin", base="002A0D5B", mass_kg=10.0, impulse_control=True))

    def test_the_plan_marks_the_control_and_needs_the_feature(self):
        self.assertTrue(self.t["impulse_control"])
        self.assertNotIn("impulse_control", tq.movable_test(0, ITEM))
        self.assertIn("impulse_control", runner_features.FEATURES)
        self.assertEqual(runner_features.needs([self.t]), ["impulse", "impulse_control", "push_judge"])
        with self.assertRaises(SystemExit):
            tq.movable_test(0, dict(ITEM, impulse_control=True, impulse_dv=[]))

    def test_the_walk_decides_and_the_ladder_is_detail(self):
        walked = dict(item_after="-3.00 6.10 0.00")
        v, c, d = tq.judge(self.t, control_obs(self.d, impulses=[imp("-3.00 4.90 0.00")], **walked), self.d)
        self.assertEqual((v, c), ("PASS", "WALKED"), d)
        self.assertIn("impulse control: ApplyHavokImpulse 37.5 (dv 1.5 m/s, step 1) moved it 1.20 m", d)
        v, c, d = tq.judge(self.t, control_obs(self.d, impulses=[imp("-3.00 6.10 0.00")] * 3, **walked), self.d)
        self.assertEqual((v, c), ("PASS", "WALKED"), d)
        self.assertIn("did not move it either: in this queue a FAIL STUCK does not show a body that does not respond", d)
        v, c, d = tq.judge(self.t, control_obs(self.d, **walked), self.d)
        self.assertIn("impulse control: the ladder did not finish (no impulse was applied)", d)
        # without the key nothing is added (an older plan reads as before)
        v, c, d = tq.judge(tq.movable_test(0, ITEM), control_obs(self.d, **walked), self.d)
        self.assertNotIn("impulse control", d)

    def test_qstep_runs_the_ladder_after_any_walk_of_a_control(self):
        with open(os.path.join(ROOT, "scripts", "game", "qstep.ps1"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("($d -lt $min -or $t.impulse_control -eq $true)) { Push-Impulses", src)


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
        self.assertEqual(q["needs"], ["impulse", "push_judge"])
        self.assertEqual(q["pre_launch"][-2:], ["check", "impulse,push_judge"])   # the runner's own runner_features.py
        self.assertEqual(q["launch_cell"], "Vault111Cryo")
        jdump([dict(ITEM, label="same"), dict(ITEM, label="same")], os.path.join(exp, "plan.json"))
        with self.assertRaises(SystemExit):
            tq.plan_movable(a)


class FakeControls:
    last_sent_tick = None
    state_dir = None                                      # no runner state folder: no open vanilla baseline

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
        self.assertIn("push_judge", runner_features.FEATURES)
        # push_judge: a runner of 91f3d17 (impulse only) would pass an item the player cannot push as PASS IMPULSE
        self.assertEqual(runner_features.needs([tq.movable_test(0, ITEM)]), ["impulse", "push_judge"])
        self.assertEqual(runner_features.needs([{"kind": "movable"}]), [])
        self.assertEqual(runner_features.needs([{"kind": "movable", "impulses": tq.impulse_steps(1, 0)}]),
                         ["impulse", "push_judge"])
        self.assertEqual(runner_features.missing(["impulse", "push_judge"]), [])

    def test_step_timeouts_cover_the_ladder(self):
        t = tq.movable_test(0, dict(ITEM, set_mass_kg=5, mass_probe=True))
        self.assertGreater(tq.step_timeout(t), 1500)
        # the reading after SetRigidBodyMass: a second selection (two sessions), its capture and the wait
        plain = tq.movable_test(0, dict(ITEM, mass_probe=True))
        self.assertGreaterEqual(tq.step_timeout(t) - tq.step_timeout(plain), 4 * tq.NPC_SESSION_S)
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
