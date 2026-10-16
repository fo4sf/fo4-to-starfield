"""The controller lease (docs/ai/leader-core.md section 6, task T2): synthetic folders only; nothing touches a game."""
import contextlib
import datetime
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from fo4sf.core import controller as c  # noqa: E402
from fo4sf.core.model import parse_iso  # noqa: E402
from fo4sf.core.state import fold  # noqa: E402

T0 = "2026-10-16T12:00:00+00:00"


def at(minutes):
    return (parse_iso(T0) + datetime.timedelta(minutes=minutes)).isoformat()


class LeaseRuleTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = os.path.join(d.name, "leader")
        self.ctl = c.Controller(self.dir, by="test")

    def events(self):
        return [(e.ev, e.fields) for e in self.ctl.ledger.read()]

    def test_claim_renew_release_and_the_ledger_agree(self):
        self.assertEqual(self.ctl.status(), "none")
        self.assertIn("no lease", self.ctl.valid_for("Claude"))
        lease = self.ctl.claim("Claude", "walk gate", 3600, now=T0)
        self.assertEqual((lease.owner, lease.expires), ("Claude", at(60)))
        self.assertEqual(self.ctl.status(at(10)), "held")
        self.assertIsNone(self.ctl.valid_for("Claude", at(10)))
        self.assertIn("not by Codex", self.ctl.valid_for("Codex", at(10)))
        self.assertTrue(os.path.exists(os.path.join(self.dir, "controller.json")))
        self.assertFalse(os.path.exists(os.path.join(self.dir, "controller.json.tmp")))
        self.assertEqual([k for k, _ in self.events()], ["controller_claimed"])
        renewed = self.ctl.renew("Claude", now=at(30))
        self.assertEqual((renewed.expires, renewed.renewed), (at(90), at(30)))
        with self.assertRaises(c.LeaseRefused):
            self.ctl.renew("Codex", now=at(31))
        with self.assertRaises(c.LeaseRefused):
            self.ctl.release("Codex", now=at(32))
        released = self.ctl.release("Claude", now=at(40))
        self.assertEqual((released.released, self.ctl.status(at(41))), (at(40), "released"))
        self.assertIn("released by Claude", self.ctl.valid_for("Claude", at(41)))
        self.assertEqual([k for k, _ in self.events()], ["controller_claimed", "controller_renewed", "controller_released"])
        # the fold of the same ledger tells the same story at every step
        s = fold(self.ctl.ledger.read())
        self.assertEqual(s.controller_status(at(41)), "released")
        self.assertEqual(s.controller["owner"], "Claude")
        self.assertEqual(self.ctl.read().last_activity(), at(40))

    def test_another_owner_is_refused_while_held_and_a_forced_claim_is_recorded(self):
        self.ctl.claim("Claude", "walk gate", 3600, now=T0)
        with self.assertRaises(c.LeaseRefused) as cm:
            self.ctl.claim("Codex", "review", 600, now=at(1))
        self.assertIn("held by Claude", str(cm.exception))
        with self.assertRaises(c.LeaseRefused):                        # force without a reason
            self.ctl.claim("Codex", "review", 600, now=at(1), force=True)
        lease = self.ctl.claim("Codex", "review", 600, now=at(2), force=True, reason="the owner's order on #32")
        self.assertEqual((lease.owner, lease.forced, lease.reason), ("Codex", True, "the owner's order on #32"))
        ev, f = self.events()[-1]
        self.assertEqual((ev, f["forced"], f["previous_owner"], f["reason"]),
                         ("controller_claimed", True, "Claude", "the owner's order on #32"))
        self.assertEqual(fold(self.ctl.ledger.read()).controller["owner"], "Codex")
        # the holder claiming again replaces its own lease without force
        again = self.ctl.claim("Codex", "review, longer", 1200, now=at(3))
        self.assertEqual((again.expires, self.events()[-1][1]["previous_expires"]), (at(23), lease.expires))

    def test_expired_lease_is_ambiguous_until_the_holder_acts_or_a_claim_is_forced(self):
        self.ctl.claim("Claude", "walk gate", 60, now=T0)
        self.assertEqual(self.ctl.status(at(5)), "ambiguous")
        self.assertIn("ambiguous", self.ctl.valid_for("Claude", at(5)))
        with self.assertRaises(c.LeaseRefused):
            self.ctl.renew("Claude", now=at(5))                          # expired: renewing is over, claim again
        with self.assertRaises(c.LeaseRefused) as cm:
            self.ctl.claim("Codex", "review", 600, now=at(5))
        self.assertIn("ambiguous", str(cm.exception))
        self.assertEqual(fold(self.ctl.ledger.read()).controller_status(at(5)), "ambiguous")
        lease = self.ctl.claim("Claude", "walk gate", 3600, now=at(5))   # the holder's own: allowed, the gap recorded
        self.assertEqual(self.events()[-1][1]["expired_for_s"], 240)
        self.assertEqual(self.ctl.status(at(6)), "held")
        self.assertIsNone(self.ctl.valid_for("Claude", at(6)))
        # the holder releases its expired lease; then anyone claims without force
        self.ctl.claim("Claude", "short", 60, now=at(10))
        self.ctl.release("Claude", now=at(20))
        self.assertEqual(self.ctl.status(at(21)), "released")
        self.ctl.claim("Codex", "review", 600, now=at(22))
        self.assertEqual(self.ctl.read().owner, "Codex")
        del lease

    def test_forced_release_needs_a_reason_and_is_marked(self):
        self.ctl.claim("Claude", "walk gate", 3600, now=T0)
        with self.assertRaises(c.LeaseRefused):
            self.ctl.release("owner", now=at(1), force=True)
        self.ctl.release("owner", now=at(1), force=True, reason="the PC is mine")
        ev, f = self.events()[-1]
        self.assertEqual((ev, f["owner"], f["released_by"], f["forced"]), ("controller_released", "Claude", "owner", True))
        with self.assertRaises(c.LeaseRefused):
            self.ctl.release("Claude", now=at(2))                        # already released

    def test_unreadable_lease_file_blocks(self):
        self.ctl.claim("Claude", "walk gate", 3600, now=T0)
        with open(self.ctl.lease_path, "w", encoding="utf-8") as f:
            f.write('{"owner": "Claude"}')
        with self.assertRaises(ValueError):
            self.ctl.read()
        self.assertIn("unreadable", self.ctl.valid_for("Claude", at(1)))
        with open(self.ctl.lease_path, "w", encoding="utf-8") as f:
            f.write("not json")
        self.assertIn("unreadable", self.ctl.valid_for("Claude", at(1)))

    def test_naive_timestamps_read_as_utc(self):
        self.assertEqual(parse_iso("2026-10-16T12:00:00"), parse_iso(T0))
        self.assertEqual(parse_iso("2026-10-16T12:00:00Z"), parse_iso(T0))


class CliTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.dir = os.path.join(d.name, "leader")

    def run_cli(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = c.main(list(argv))
        return code, out.getvalue().strip()

    def test_claim_status_require_release(self):
        code, out = self.run_cli("status", "--dir", self.dir, "--require", "Claude")
        self.assertEqual((code, out.splitlines()[-1][:20]), (1, "not valid for Claude"))
        code, out = self.run_cli("claim", "--dir", self.dir, "--owner", "Claude", "--purpose", "walk gate", "--ttl", "600")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.startswith("claimed by Claude until "))
        self.assertEqual(self.run_cli("status", "--dir", self.dir, "--require", "Claude")[0], 0)
        self.assertEqual(self.run_cli("status", "--dir", self.dir, "--require", "Codex")[0], 1)
        code, out = self.run_cli("claim", "--dir", self.dir, "--owner", "Codex", "--purpose", "review")
        self.assertEqual((code, out[:8]), (1, "refused:"))
        code, out = self.run_cli("renew", "--dir", self.dir, "--owner", "Claude", "--ttl", "1200")
        self.assertEqual((code, out[:7]), (0, "renewed"))
        code, out = self.run_cli("status", "--dir", self.dir, "--json")
        j = json.loads(out)
        self.assertEqual((j["status"], j["lease"]["owner"], j["lease"]["ttl_s"]), ("held", "Claude", 1200))
        self.assertEqual(j["last_activity"], j["lease"]["renewed"])
        code, out = self.run_cli("release", "--dir", self.dir, "--owner", "Claude")
        self.assertEqual((code, out[:9]), (0, "released:"))
        j = json.loads(self.run_cli("status", "--dir", self.dir, "--json")[1])
        self.assertEqual(j["status"], "released")
        # the ledger beside the lease has every step, written by the owner named
        from fo4sf.core.state import Ledger
        self.assertEqual([(e.ev, e.by) for e in Ledger(os.path.join(self.dir, "ledger.jsonl")).read()],
                         [("controller_claimed", "Claude"), ("controller_renewed", "Claude"), ("controller_released", "Claude")])

    def test_status_json_without_a_lease_and_forced_claim(self):
        j = json.loads(self.run_cli("status", "--dir", self.dir, "--json")[1])
        self.assertEqual((j["status"], j["lease"], j["last_activity"]), ("none", None, None))
        self.assertEqual(self.run_cli("claim", "--dir", self.dir, "--owner", "watchdog", "--purpose", "chain",
                                      "--ttl", "1", "--force", "--reason", "idle")[0], 0)
        import time
        time.sleep(1.1)
        j = json.loads(self.run_cli("status", "--dir", self.dir, "--json")[1])
        self.assertEqual(j["status"], "ambiguous")
        code, out = self.run_cli("claim", "--dir", self.dir, "--owner", "Claude", "--purpose", "window")
        self.assertEqual((code, out[:8]), (1, "refused:"))
        self.assertEqual(self.run_cli("claim", "--dir", self.dir, "--owner", "Claude", "--purpose", "window",
                                      "--force", "--reason", "the owner is back")[0], 0)


if __name__ == "__main__":
    unittest.main()
